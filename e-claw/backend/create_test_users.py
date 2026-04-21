"""
创建 e-claw 测试用户
"""
import asyncio
import uuid
from datetime import datetime

from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models import User, UserRole, Tenant


async def create_test_users():
    """创建测试用户"""
    
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        # 检查并获取默认租户
        from sqlalchemy import select
        result = await db.execute(select(Tenant).where(Tenant.code == "DEFAULT"))
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant_id = str(tenant.id)
            print(f"✓ 租户已存在: 默认租户(ID: {tenant_id})")
        else:
            tenant_id = str(uuid.uuid4())
            tenant = Tenant(
                id=tenant_id,
                name="默认租户",
                code="DEFAULT",
                description="系统默认租户",
                status="active",
                total_quota=10000000,
                used_quota=0
            )
            db.add(tenant)
            await db.commit()
            print(f"✓ 租户创建完成: 默认租户(ID: {tenant_id})")
        
        # 检查并获取研发部门租户
        result = await db.execute(select(Tenant).where(Tenant.code == "RD"))
        tenant2 = result.scalar_one_or_none()
        if tenant2:
            tenant_id_2 = str(tenant2.id)
            print(f"✓ 租户已存在: 研发部门(ID: {tenant_id_2})")
        else:
            tenant_id_2 = str(uuid.uuid4())
            tenant2 = Tenant(
                id=tenant_id_2,
                name="研发部门",
                code="RD",
                description="研发部门租户",
                status="active",
                total_quota=5000000,
                used_quota=0
            )
            db.add(tenant2)
            await db.commit()
            print(f"✓ 租户创建完成: 研发部门(ID: {tenant_id_2})")
        
        # 测试用户列表
        test_users = [
            {
                "username": "admin",
                "email": "admin@eclaw.com",
                "full_name": "超级管理员",
                "password": "admin123",
                "role": UserRole.SUPER_ADMIN,
                "tenant_id": tenant_id,
                "personal_quota": 1000000
            },
            {
                "username": "dept_admin",
                "email": "dept_admin@eclaw.com",
                "full_name": "部门管理员",
                "password": "admin123",
                "role": UserRole.DEPT_ADMIN,
                "tenant_id": tenant_id_2,
                "personal_quota": 500000
            },
            {
                "username": "employee",
                "email": "employee@eclaw.com",
                "full_name": "普通员工",
                "password": "admin123",
                "role": UserRole.EMPLOYEE,
                "tenant_id": tenant_id_2,
                "personal_quota": 100000
            },
            {
                "username": "ops",
                "email": "ops@eclaw.com",
                "full_name": "运维人员",
                "password": "admin123",
                "role": UserRole.OPS,
                "tenant_id": tenant_id,
                "personal_quota": 200000
            }
        ]
        
        for user_data in test_users:
            # 检查用户是否已存在
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"⚠ 用户 {user_data['username']} 已存在，跳过")
                continue
            
            # 创建用户
            user = User(
                id=str(uuid.uuid4()),
                username=user_data["username"],
                email=user_data["email"],
                full_name=user_data["full_name"],
                hashed_password=get_password_hash(user_data["password"]),
                role=user_data["role"],
                tenant_id=user_data["tenant_id"],
                personal_quota=user_data["personal_quota"],
                personal_used=0,
                status="active"
            )
            db.add(user)
            print(f"✓ 创建用户: {user_data['username']} ({user_data['role'].value})")
        
        await db.commit()
    
    print("\n" + "="*50)
    print("测试用户创建完成！")
    print("="*50)
    print("\n用户列表:")
    print("-" * 50)
    print(f"1. 超级管理员 | 用户名: admin    | 密码: admin123")
    print(f"2. 部门管理员 | 用户名: dept_admin | 密码: admin123")
    print(f"3. 普通员工   | 用户名: employee  | 密码: admin123")
    print(f"4. 运维人员   | 用户名: ops       | 密码: admin123")
    print("-" * 50)


if __name__ == "__main__":
    asyncio.run(create_test_users())