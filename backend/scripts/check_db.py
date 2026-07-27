import sqlite3

conn = sqlite3.connect('backend/data/bots/main/knowledge.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for t in tables:
    print(f'\n=== {t[0]} ===')
    cursor.execute(f'PRAGMA table_info({t[0]})')
    for col in cursor.fetchall():
        print(f'  {col[1]} ({col[2]})')
    cursor.execute(f'SELECT COUNT(*) FROM {t[0]}')
    print(f'  rows: {cursor.fetchone()[0]}')
conn.close()
