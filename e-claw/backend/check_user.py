import asyncio
from app.core.database import AsyncSessionLocal
from app.core.security import verify_password
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT id, username, hashed_password FROM users WHERE username = 'admin'"))
        row = result.fetchone()
        if row:
            print(f'User: {row[1]}')
            print(f'Hash: {row[2][:50]}...')
            test_pw = 'admin123'[:72]
            print(f'Test password (truncated): {test_pw}')
            result = verify_password(test_pw, row[2])
            print(f'Verify result: {result}')
        else:
            print('User not found')

asyncio.run(check())