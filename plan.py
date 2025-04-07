import pandas as pd
from telegram import InputFile
from telegram.ext import CallbackContext
import sqlite3
import os

# Подключение к базе данных
conn = sqlite3.connect('Users_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Получение пользователей на вахте
def get_users_on_shift():
    cursor.execute('SELECT tab_number, name, t_number FROM Users_user_bot WHERE is_on_shift = ?', (True,))
    return cursor.fetchall()

# Отправка уведомлений
def send_reminders(context: CallbackContext):
    users_on_shift = get_users_on_shift()
    file_name = 'counters.xlsx'  # Имя существующего файла

    # Проверяем, существует ли файл
    if not os.path.exists(file_name):
        print(f"Файл {file_name} не найден.")
        return

    for user in users_on_shift:
        tab_number, name, t_number = user
        user_data = {'tab_number': tab_number, 'name': name, 't_number': t_number}
        
        # Отправка файла пользователю
        with open(file_name, 'rb') as file:
            context.bot.send_document(
                chat_id=t_number,
                document=InputFile(file),
                caption=f"Уважаемый(ая) {name}, пожалуйста, заполните показания счётчиков до пятницы 14:00 МСК."
            )

# Еженедельное задание
def weekly_reminder(context: CallbackContext):
    send_reminders(context)