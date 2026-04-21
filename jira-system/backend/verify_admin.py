"""Verify admin user"""
import sqlite3

conn = sqlite3.connect('jira.db')
cursor = conn.cursor()
cursor.execute("SELECT id, username, email, is_superuser FROM users WHERE username='admin'")
user = cursor.fetchone()
if user:
    print(f'User verified in database:')
    print(f'  ID: {user[0]}')
    print(f'  Username: {user[1]}')
    print(f'  Email: {user[2]}')
    print(f'  is_superuser: {bool(user[3])}')
else:
    print('User not found!')
conn.close()