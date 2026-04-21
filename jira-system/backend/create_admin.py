"""Script to create admin user"""
import uuid
import sqlite3
import bcrypt

# First check if user exists
conn = sqlite3.connect('jira.db')
cursor = conn.cursor()

# Check if users table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if cursor.fetchone() is None:
    print('Users table does not exist yet. The database needs to be initialized first.')
    conn.close()
else:
    # Check if admin exists
    cursor.execute("SELECT id, username FROM users WHERE username='admin'")
    existing = cursor.fetchone()
    if existing:
        print(f'User admin already exists with id: {existing[0]}')
    else:
        # Hash password using bcrypt
        hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert admin user
        user_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO users (id, email, username, full_name, hashed_password, is_active, is_superuser, oauth_provider, oauth_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ''', (user_id, 'admin@example.com', 'admin', 'Administrator', hashed, 1, 1, None, None))
        conn.commit()
        print(f'Admin user created successfully with id: {user_id}')
    
    conn.close()
