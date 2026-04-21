"""
Initialize E-Claw database with default users
"""

import asyncio
import sys

sys.path.insert(0, "C:/eswin/emaas/AI-Coding/e-claw/backend")

from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models import User, UserRole, Tenant
from sqlalchemy import select
import uuid


async def init_db():
    """Initialize database with default data"""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create DEFAULT tenant
        result = await db.execute(select(Tenant).where(Tenant.code == "DEFAULT"))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Default Tenant",
                code="DEFAULT",
                description="System default tenant",
                status="active",
                total_quota=10000000,
                used_quota=0,
            )
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
            print("Created DEFAULT tenant")

        # Create admin user
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@e-claw.com",
                full_name="Super Admin",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.SUPER_ADMIN,
                tenant_id=None,
                status="active",
            )
            db.add(admin)
            await db.commit()
            print("Created admin user (username: admin, password: admin123)")

        # Create department admin
        result = await db.execute(select(User).where(User.username == "dept_admin"))
        dept_admin = result.scalar_one_or_none()
        if not dept_admin:
            dept_admin = User(
                id=str(uuid.uuid4()),
                username="dept_admin",
                email="dept_admin@e-claw.com",
                full_name="Department Admin",
                hashed_password=get_password_hash("dept123"),
                role=UserRole.DEPT_ADMIN,
                tenant_id=tenant.id,
                status="active",
            )
            db.add(dept_admin)
            await db.commit()
            print("Created dept_admin user (username: dept_admin, password: dept123)")

        # Create regular user
        result = await db.execute(select(User).where(User.username == "user"))
        regular_user = result.scalar_one_or_none()
        if not regular_user:
            regular_user = User(
                id=str(uuid.uuid4()),
                username="user",
                email="user@e-claw.com",
                full_name="Regular User",
                hashed_password=get_password_hash("user123"),
                role=UserRole.EMPLOYEE,
                tenant_id=tenant.id,
                status="active",
            )
            db.add(regular_user)
            await db.commit()
            print("Created user account (username: user, password: user123)")

        print("\nDatabase initialization complete!")
        print("Default users:")
        print("  - admin / admin123 (Super Admin)")
        print("  - dept_admin / dept123 (Department Admin)")
        print("  - user / user123 (Employee)")


if __name__ == "__main__":
    asyncio.run(init_db())
