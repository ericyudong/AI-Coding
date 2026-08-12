"""Bootstrap default admin, departments, and sample partners."""
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.roles import Role
from app.core.security import hash_password
from app.models.models import User
from app.models.performance_models import Customer, Department, Supplier


async def ensure_departments() -> dict[str, int]:
    defaults = [
        ("法务部", "LEGAL"),
        ("销售一部", "SALES1"),
        ("采购部", "PROC"),
        ("财务部", "FIN"),
        ("管理层", "MGMT"),
    ]
    mapping: dict[str, int] = {}
    async with SessionLocal() as db:
        for name, code in defaults:
            result = await db.execute(select(Department).where(Department.name == name))
            dept = result.scalar_one_or_none()
            if not dept:
                dept = Department(name=name, code=code)
                db.add(dept)
                await db.flush()
            mapping[name] = dept.id
        await db.commit()
    return mapping


async def ensure_admin_user() -> None:
    settings = get_settings()
    depts = await ensure_departments()
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == settings.bootstrap_admin_username))
        admin = result.scalar_one_or_none()
        if admin:
            changed = False
            if admin.role != Role.SYSTEM_ADMIN:
                admin.role = Role.SYSTEM_ADMIN
                changed = True
            if not admin.department_id:
                admin.department_id = depts.get("法务部")
                changed = True
            if changed:
                await db.commit()
            return
        any_user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        if any_user:
            return
        if not settings.bootstrap_admin_enabled:
            return
        user = User(
            username=settings.bootstrap_admin_username,
            email=f"{settings.bootstrap_admin_username}@yihui.tech",
            hashed_password=hash_password(settings.bootstrap_admin_password),
            display_name="管理员",
            role=Role.SYSTEM_ADMIN,
            department_id=depts.get("法务部"),
            is_active=True,
        )
        db.add(user)
        await db.commit()


async def seed_partners() -> None:
    """Seed demo suppliers/customers if empty."""
    async with SessionLocal() as db:
        result = await db.execute(select(Supplier).limit(1))
        if result.scalar_one_or_none():
            return
        admin = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        uid = admin.id if admin else 1
        dept_id = admin.department_id if admin else None
        suppliers = [
            Supplier(
                user_id=uid,
                department_id=dept_id,
                name="华为技术有限公司",
                credit_code="91440300708461136T",
                industry="ICT",
                contract_count=12,
                total_amount=32000000,
                risk_level="low",
                delay_count=1,
            ),
            Supplier(
                user_id=uid,
                department_id=dept_id,
                name="阿里云计算有限公司",
                industry="云计算",
                contract_count=5,
                total_amount=8600000,
                risk_level="medium",
                delay_count=2,
            ),
        ]
        customers = [
            Customer(
                user_id=uid,
                department_id=dept_id,
                name="腾讯科技有限公司",
                industry="互联网",
                contract_count=52,
                order_count=203,
                total_sales=580000000,
                total_qty=1200,
                risk_level="low",
            ),
            Customer(
                user_id=uid,
                department_id=dept_id,
                name="腾讯云计算有限公司",
                industry="云计算",
                contract_count=8,
                order_count=40,
                total_sales=120000000,
                risk_level="low",
            ),
            Customer(
                user_id=uid,
                department_id=dept_id,
                name="字节跳动有限公司",
                industry="互联网",
                contract_count=18,
                order_count=66,
                total_sales=96000000,
                risk_level="medium",
                payment_delay_count=3,
            ),
        ]
        for s in suppliers:
            db.add(s)
        for c in customers:
            db.add(c)
        await db.commit()
