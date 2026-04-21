"""
E-Claw 数据库管理
"""
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Base

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """初始化数据库 - 创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建默认租户和超级管理员
    await create_default_data()


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_default_data():
    """创建默认数据"""
    from app.models import Tenant, User, UserRole
    from app.core.security import get_password_hash
    from datetime import datetime
    import uuid
    
    async with AsyncSessionLocal() as session:
        # 检查是否已存在默认租户
        from sqlalchemy import select
        result = await session.execute(
            select(Tenant).where(Tenant.code == "DEFAULT")
        )
        default_tenant = result.scalar_one_or_none()
        
        if not default_tenant:
            # 创建默认租户
            default_tenant = Tenant(
                id=uuid.uuid4(),
                name="默认租户",
                code="DEFAULT",
                description="系统默认租户",
                total_quota=10000000,
                status="active"
            )
            session.add(default_tenant)
            
            # 创建超级管理员
            super_admin = User(
                id=uuid.uuid4(),
                tenant_id=None,  # 超级管理员不属于任何租户
                username="admin",
                email="admin@e-claw.local",
                full_name="系统管理员",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.SUPER_ADMIN,
                status="active",
                personal_quota=99999999
            )
            session.add(super_admin)
            
            await session.commit()


# 依赖注入
Dependency = get_db