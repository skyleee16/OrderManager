# database.py
import sqlite3
import pandas as pd

DB_NAME = 'clients.db'

def init_db():
    """Создает таблицу clients, если её нет"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            status TEXT DEFAULT 'new',
            note TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_companies_from_excel(file_path):
    """Загружает компании из Excel в базу данных"""
    df = pd.read_excel(file_path) # Читаем Excel файл
    conn = sqlite3.connect(DB_NAME)
    for _, row in df.iterrows():
        # Здесь укажи название столбцов из твоей таблицы
        company_name = row['Название']
        company_phone = row['Адрес']
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO clients (name, phone) VALUES (?, ?)
            ON CONFLICT DO NOTHING
        ''', (company_name, company_phone))
    conn.commit()
    conn.close()