import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
import sqlite3
from buttons_handler import handle_resignation, handle_metrics, get_vacation_conversation_handler

# Состояния для ConversationHandler
ENTER_TAB_NUMBER, = range(1)

conn = sqlite3.connect('Users_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users_admin_bot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_number INTEGER UNIQUE,
    name TEXT,
    role TEXT,
    t_number INTEGER,
    location TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Users_user_bot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_number INTEGER UNIQUE,
    name TEXT,
    role TEXT,
    t_number INTEGER,
    is_on_shift BOOLEAN NOT NULL,
    location TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Users_dir_bot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_number INTEGER UNIQUE,
    name TEXT,
    t_number INTEGER,
    role TEXT,
    location TEXT
)''')
conn.commit()

# Загрузка таблицы пользователей
def load_users_table():
    # Пример загрузки из Excel файла
    df = pd.read_excel('users.xlsx')
    return df

# Обработка команды /start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Привет! Введите ваш табельный номер:")
    return ENTER_TAB_NUMBER

# Обработка введенного табельного номера
def handle_tab_number(update: Update, context: CallbackContext) -> int:
    tab_number = update.message.text
    df = load_users_table()
    
    # Поиск пользователя по табельному номеру
    user = df[df['Табельный номер'] == int(tab_number)]
    
    if not user.empty:
        name = user['ФИО'].values[0]
        role = determine_role(user)
        t_number = user['Номер телефона'].values[0]
        location = user['Локация'].values[0]  # Предположим, что локация хранится в столбце 'Локация'
        context.user_data['role'] = role
        context.user_data['tab_number'] = int(tab_number)  # Сохраняем табельный номер
        
        if not is_user_in_db(int(tab_number), role):
            add_user_to_db(int(tab_number), name, role, t_number, location)
            update.message.reply_text(f"Здравствуйте, {name}! Ваша роль: {role}. Локация: {location}.")
        else:
            update.message.reply_text(f"Здравствуйте, {name}! Вы уже зарегистрированы в системе.")
        
        show_role_specific_menu(update, role)
    else:
        update.message.reply_text("Пользователь с таким табельным номером не найден.")
    
    return ConversationHandler.END

# Определение роли пользователя
def determine_role(user):
    role = user['Роль'].values[0]
    location = user['Локация'].values[0]
    
    if 'Администратор' in role:
        return 'Администратор'
    elif 'Руководитель' in role:
        return 'Руководитель'
    else:
        return 'Пользователь'

# Показ меню в зависимости от роли
def show_role_specific_menu(update: Update, role: str):
    keyboard = [['Я уволился', 'Я в отпуске', 'Записать показания']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    if role == 'Администратор':
        update.message.reply_text("Доступные команды для администратора: /admin_command", reply_markup=reply_markup)
    elif role == 'Руководитель':
        update.message.reply_text("Доступные команды для руководителя: /manager_command", reply_markup=reply_markup)
    else:
        update.message.reply_text("Доступные команды для пользователя: /user_command", reply_markup=reply_markup)


def handle_button(update: Update, context: CallbackContext):
    text = update.message.text
    if text == 'Я уволился':
        update.message.reply_text("Вы уволились. Ваш аккаунт будет удален.")
        # Удаление пользователя из базы данных
        delete_user(update.message.from_user.id)
    elif text == 'Я в отпуске':
        update.message.reply_text("Вы в отпуске. Ваш статус обновлен.")
        # Обновление статуса пользователя в базе данных
        set_user_on_vacation(update.message.from_user.id)


# Удаление пользователя из базы данных
def delete_user(user_id):
    cursor.execute('DELETE FROM Users_admin_bot WHERE id = ?', (user_id,))
    cursor.execute('DELETE FROM Users_dir_bot WHERE id = ?', (user_id,))
    cursor.execute('DELETE FROM Users_user_bot WHERE id = ?', (user_id,))
    conn.commit()

# Установка статуса "В отпуске"
def set_user_on_vacation(user_id):
    cursor.execute('UPDATE Users_user_bot SET is_on_shift = ? WHERE id = ?', (False, user_id))
    conn.commit()


# Проверка, существует ли пользователь в базе данных
def is_user_in_db(tab_number, role):
    if role == 'Администратор':
        cursor.execute('SELECT * FROM Users_admin_bot WHERE tab_number = ?', (tab_number,))
    elif role == 'Руководитель':
        cursor.execute('SELECT * FROM Users_dir_bot WHERE tab_number = ?', (tab_number,))
    else:
        cursor.execute('SELECT * FROM Users_user_bot WHERE tab_number = ?', (tab_number,))
    
    return cursor.fetchone() is not None

# Добавление пользователя в соответствующую таблицу базы данных
def add_user_to_db(tab_number, name, role, t_number, location):
    if role == 'Администратор':
        cursor.execute('INSERT INTO Users_admin_bot (tab_number, name, role, t_number, location) VALUES (?, ?, ?, ?, ?)', 
                       (tab_number, name, role, t_number, location))
    elif role == 'Руководитель':
        cursor.execute('INSERT INTO Users_dir_bot (tab_number, name, role, t_number, location) VALUES (?, ?, ?, ?, ?)', 
                       (tab_number, name, role, t_number, location))
    else:
        cursor.execute('INSERT INTO Users_user_bot (tab_number, name, role, t_number, is_on_shift, location) VALUES (?, ?, ?, ?, ?, ?)', 
                       (tab_number, name, role, t_number, False, location))  # is_on_shift по умолчанию False
    conn.commit()

# Обработка команды /cancel
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

def main():
    updater = Updater("7575482607:AAG9iLYAO2DFpjHVBDn3-m-tLicdNXBsyBQ")
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ENTER_TAB_NUMBER: [MessageHandler(Filters.text & ~Filters.command, handle_tab_number)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Добавляем ConversationHandler для отпуска
    dispatcher.add_handler(get_vacation_conversation_handler())

    # Добавляем обработчики кнопок
    dispatcher.add_handler(MessageHandler(Filters.regex('^Я уволился$'), handle_resignation))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Записать показания$'), handle_metrics))
    dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()