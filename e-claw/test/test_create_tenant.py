import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, 'c:/eswin/emaas/e-claw/backend')
os.chdir('c:/eswin/emaas/e-claw/backend')

async def test_create_tenant():
    from app.core.database import AsyncSessionLocal
    from app.models import Tenant
    from sqlalchemy import select
    import uuid
    
    async with AsyncSessionLocal() as db:
        # Check if test tenant exists
        result = await db.execute(
            select(Tenant).where(Tenant.code == "TEST")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Test tenant already exists: {existing.name}")
            return
        
        # Create a new tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Tenant",
            code="TEST",
            description="Test description for tenant",
            total_quota=1000000,
            used_quota=0,
            status="active"
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        
        print(f"Tenant created successfully: {tenant.id}, {tenant.name}, {tenant.code}")

if __name__ == '__main__':
    asyncio.run(test_create_tenant())