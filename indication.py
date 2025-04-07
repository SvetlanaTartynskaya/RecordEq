import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz
from threading import Timer
import os
from openpyxl.styles import Font


# Настройки
DB_NAME = 'Users_bot.db'  # Для пользователей и администраторов
EXCEL_EQUIPMENT_FILE = 'equipment_data.xlsx'  # Файл с данными оборудования
EXCEL_FILES_DIR = 'excel_reports'

# Создаем директорию для Excel файлов, если ее нет
os.makedirs(EXCEL_FILES_DIR, exist_ok=True)

def get_current_time():
    """Возвращает текущее время в московском часовом поясе"""
    tz = pytz.timezone('Europe/Moscow')
    return datetime.now(tz)

def is_wednesday_8am():
    """Проверяет, является ли текущий момент средой 8:00 по МСК"""
    now = get_current_time()
    return now.weekday() == 2 and now.hour == 8 and now.minute == 0

def get_next_wednesday_8am():
    """Возвращает следующий момент времени - среда 8:00 по МСК"""
    now = get_current_time()
    days_ahead = (2 - now.weekday()) % 7  # 2 - это среда
    if days_ahead == 0 and now.hour >= 8:
        days_ahead = 7  # Переходим на следующую среду
    next_wednesday = now + timedelta(days=days_ahead)
    next_wednesday = next_wednesday.replace(hour=8, minute=0, second=0, microsecond=0)
    return next_wednesday

def schedule_weekly_check(bot):
    """Планирует еженедельную проверку на следующую среду 8:00"""
    next_wednesday = get_next_wednesday_8am()
    now = get_current_time()
    delta = (next_wednesday - now).total_seconds()
    
    # Запускаем таймер
    t = Timer(delta, weekly_check, args=[bot])
    t.start()

def weekly_check(bot):
    """Основная функция еженедельной проверки"""
    if is_wednesday_8am():
        send_reminders(bot)
    
    # Планируем следующую проверку
    schedule_weekly_check(bot)

def send_reminders(bot):
    """Отправляет напоминания пользователям на вахте"""
    try:
        # Подключаемся к базе данных пользователей
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем пользователей на вахте
        cursor.execute("SELECT tab_number, name FROM Users_user_bot WHERE is_on_shift = 1")
        users_on_shift = cursor.fetchall()
        
        # Читаем данные оборудования из Excel
        try:
            equipment_df = pd.read_excel(EXCEL_EQUIPMENT_FILE)
        except Exception as e:
            print(f"Ошибка при чтении файла оборудования: {e}")
            return
        
        for tab_number, name in users_on_shift:
            try:
                # Получаем оборудование для локации пользователя
                # Предполагаем, что в таблице пользователей есть поле location_id
                cursor.execute("SELECT location FROM Users_user_bot WHERE tab_number = ?", (tab_number,))
                location_id = cursor.fetchone()[0]
                
                # Фильтруем оборудование по location_id
                user_equipment = equipment_df[equipment_df['location'] == location_id]
                
                if not user_equipment.empty:
                    # Создаем Excel файл
                    file_path = create_excel_report(tab_number, user_equipment)
                    
                    # Отправляем сообщение с файлом
                    message = (
                        f"Уважаемый(ая) {name}!\n"
                        "Напоминаем, что в пятницу до 14:00 МСК вам необходимо подать данные о показаниях счётчиков.\n"
                        "Пожалуйста, заполните приложенный файл и отправьте его обратно в этом чате."
                    )
                    
                    with open(file_path, 'rb') as file:
                        bot.send_document(chat_id=tab_number, document=file, caption=message)
                
            except Exception as e:
                print(f"Ошибка при отправке напоминания пользователю {tab_number}: {e}")
        
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        if conn:
            conn.close()

def create_excel_report(name, equipment_df):
    """Создает Excel файл с данными оборудования"""
    # Создаем новый DataFrame для отчета
    report_df = pd.DataFrame()
    
    # Добавляем необходимые колонки
    report_df['№ п/п'] = range(1, len(equipment_df) + 1)
    report_df['Гос. номер'] = equipment_df['gov_number']
    report_df['Инв. №'] = equipment_df['inventory_number']
    report_df['Счётчик'] = equipment_df['counter_name']
    report_df['Показания'] = equipment_df['last_counter_value']
    report_df['Комментарий'] = ""
    
    # Сохраняем файл
    filename = f"counter_readings_{name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    file_path = os.path.join(EXCEL_FILES_DIR, filename)
    
    # Сохраняем с форматированием
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        report_df.to_excel(writer, index=False, sheet_name='Показания счетчиков')
        
        # Получаем workbook и worksheet для дополнительного форматирования
        workbook = writer.book
        worksheet = writer.sheets['Показания счетчиков']
        
        # Жирный шрифт для заголовков
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        
        # Автоподбор ширины столбцов
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return file_path

def notify_admins(bot, tab_number, file_path):
    """Уведомляет администраторов о получении файла от пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем информацию о пользователе
        cursor.execute("SELECT name FROM Users_user_bot WHERE tab_number = ?", (tab_number,))
        user_name = cursor.fetchone()[0]
        
        # Получаем список администраторов
        cursor.execute("SELECT tab_number FROM Users_admin_bot")
        admins = cursor.fetchall()
        
        message = f"Пользователь {user_name} отправил показания счетчиков."
        
        for admin_id, in admins:
            try:
                with open(file_path, 'rb') as file:
                    bot.send_document(chat_id=admin_id, document=file, caption=message)
            except Exception as e:
                print(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")
        
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        if conn:
            conn.close()

def setup_weekly_scheduler(bot):
    """Настраивает еженедельное расписание"""
    schedule_weekly_check(bot)

def handle_user_file(bot, message):
    """Обрабатывает файл, отправленный пользователем"""
    user_id = message.from_user.id
    
    # Проверяем, что это Excel файл
    if not message.document.file_name.endswith('.xlsx'):
        bot.reply_to(message, "Ошибка: пожалуйста, отправьте файл в формате Excel (.xlsx)")
        return
    
    try:
        # Скачиваем файл
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем файл
        filename = f"user_response_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path = os.path.join(EXCEL_FILES_DIR, filename)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Уведомляем администраторов
        notify_admins(bot, user_id, file_path)
        
        bot.reply_to(message, "Спасибо! Ваши показания получены и переданы администраторам.")
        
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при обработке файла: {e}")