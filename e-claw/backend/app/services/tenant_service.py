"""
E-Claw 多租户服务
租户管理、配额控制
"""
import uuid
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models import Tenant, User, UserRole


class TenantService:
    """租户服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()
    
    async def get_tenant_by_code(self, code: str) -> Optional[Tenant]:
        """通过代码获取租户"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.code == code)
        )
        return result.scalar_one_or_none()
    
    async def create_tenant(
        self,
        name: str,
        code: str,
        description: str = "",
        total_quota: int = 1000000
    ) -> Tenant:
        """创建租户"""
        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            code=code,
            description=description,
            total_quota=total_quota,
            status="active"
        )
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant
    
    async def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        total_quota: Optional[int] = None,
        status: Optional[str] = None
    ) -> Optional[Tenant]:
        """更新租户"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        if name is not None:
            tenant.name = name
        if description is not None:
            tenant.description = description
        if total_quota is not None:
            tenant.total_quota = total_quota
        if status is not None:
            tenant.status = status
        
        tenant.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（软删除）"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        # 检查是否有用户
        user_count = await self.db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id)
        )
        if user_count.scalar() > 0:
            return False
        
        tenant.status = "deleted"
        tenant.updated_at = datetime.utcnow()
        await self.db.commit()
        return True
    
    async def get_user_count(self, tenant_id: str) -> int:
        """获取租户用户数"""
        result = await self.db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id)
        )
        return result.scalar() or 0
    
    async def check_quota(self, tenant_id: str, required_tokens: int) -> bool:
        """检查租户配额是否足够"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        available = tenant.total_quota - (tenant.used_quota or 0)
        return available >= required_tokens
    
    async def consume_quota(self, tenant_id: str, tokens: int) -> bool:
        """消耗租户配额"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        if not await self.check_quota(tenant_id, tokens):
            return False
        
        tenant.used_quota = (tenant.used_quota or 0) + tokens
        tenant.updated_at = datetime.utcnow()
        await self.db.commit()
        return True
    
    async def release_quota(self, tenant_id: str, tokens: int):
        """释放租户配额（退回未使用的）"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return
        
        tenant.used_quota = max(0, (tenant.used_quota or 0) - tokens)
        tenant.updated_at = datetime.utcnow()
        await self.db.commit()
    
    async def list_tenants(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[Tenant]:
        """获取租户列表"""
        query = select(Tenant)
        
        if status:
            query = query.where(Tenant.status == status)
        
        query = query.order_by(Tenant.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_tenant_stats(self, tenant_id: str) -> dict:
        """获取租户统计"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        # 用户数
        user_count = await self.get_user_count(tenant_id)
        
        # 活跃用户数
        active_users = await self.db.execute(
            select(func.count(User.id)).where(
                and_(
                    User.tenant_id == tenant_id,
                    User.status == "active"
                )
            )
        )
        
        return {
            "tenant_id": str(tenant_id),
            "total_quota": tenant.total_quota,
            "used_quota": tenant.used_quota or 0,
            "available_quota": tenant.total_quota - (tenant.used_quota or 0),
            "user_count": user_count,
            "active_users": active_users.scalar() or 0
        }
    
    async def reset_tenant_quota(self, tenant_id: str):
        """重置租户配额"""
        tenant = await self.get_tenant(tenant_id)
        if tenant:
            tenant.used_quota = 0
            tenant.updated_at = datetime.utcnow()
            await self.db.commit()
    
    async def transfer_quota(
        self,
        from_tenant_id: str,
        to_tenant_id: str,
        tokens: int
    ) -> bool:
        """转移配额（仅超级管理员）"""
        from_tenant = await self.get_tenant(from_tenant_id)
        to_tenant = await self.get_tenant(to_tenant_id)
        
        if not from_tenant or not to_tenant:
            return False
        
        # 检查源租户是否有足够配额
        if (from_tenant.total_quota - (from_tenant.used_quota or 0)) < tokens:
            return False
        
        # 执行转移
        from_tenant.total_quota -= tokens
        to_tenant.total_quota += tokens
        from_tenant.updated_at = datetime.utcnow()
        to_tenant.updated_at = datetime.utcnow()
        
        await self.db.commit()
        return True