import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, 'c:/eswin/emaas/e-claw/backend')
os.chdir('c:/eswin/emaas/e-claw/backend')

async def init_db():
    from app.core.database import init_db
    print('Initializing database...')
    await init_db()
    print('Database initialized successfully!')

if __name__ == '__main__':
    asyncio.run(init_db())