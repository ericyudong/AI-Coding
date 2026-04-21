"""
E-Claw Token计量服务
Token使用跟踪和配额管理
"""
import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models import TokenUsage, User, Tenant, Task


class TokenService:
    """Token计量服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_usage(
        self,
        user_id: str,
        tenant_id: Optional[str],
        task_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> TokenUsage:
        """记录Token使用"""
        total_tokens = input_tokens + output_tokens
        
        # 创建使用记录
        usage = TokenUsage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model
        )
        
        self.db.add(usage)
        
        # 更新用户使用量
        await self._update_user_usage(user_id, total_tokens)
        
        # 更新租户使用量
        if tenant_id:
            await self._update_tenant_usage(tenant_id, total_tokens)
        
        await self.db.commit()
        await self.db.refresh(usage)
        
        return usage
    
    async def _update_user_usage(self, user_id: str, tokens: int):
        """更新用户Token使用量"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.personal_used = (user.personal_used or 0) + tokens
    
    async def _update_tenant_usage(self, tenant_id: str, tokens: int):
        """更新租户Token使用量"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.used_quota = (tenant.used_quota or 0) + tokens
    
    async def get_user_usage(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """获取用户Token使用统计"""
        query = select(
            func.sum(TokenUsage.input_tokens),
            func.sum(TokenUsage.output_tokens),
            func.sum(TokenUsage.total_tokens)
        ).where(TokenUsage.user_id == user_id)
        
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "user_id": user_id,
            "input_tokens": row[0] or 0,
            "output_tokens": row[1] or 0,
            "total_tokens": row[2] or 0,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    
    async def get_tenant_usage(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """获取租户Token使用统计"""
        query = select(
            func.sum(TokenUsage.input_tokens),
            func.sum(TokenUsage.output_tokens),
            func.sum(TokenUsage.total_tokens)
        ).where(TokenUsage.tenant_id == tenant_id)
        
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "tenant_id": tenant_id,
            "input_tokens": row[0] or 0,
            "output_tokens": row[1] or 0,
            "total_tokens": row[2] or 0,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    
    async def get_user_usage_by_model(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[dict]:
        """获取用户按模型分类的使用统计"""
        query = select(
            TokenUsage.model,
            func.sum(TokenUsage.total_tokens)
        ).where(TokenUsage.user_id == user_id)
        
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        query = query.group_by(TokenUsage.model)
        
        result = await self.db.execute(query)
        
        return [
            {"model": row[0], "total_tokens": row[1]}
            for row in result.all()
        ]
    
    async def get_task_usage(self, task_id: str) -> Optional[dict]:
        """获取任务的Token使用"""
        result = await self.db.execute(
            select(TokenUsage).where(TokenUsage.task_id == task_id)
        )
        usage = result.scalar_one_or_none()
        
        if not usage:
            return None
        
        return {
            "task_id": task_id,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "model": usage.model,
            "created_at": usage.created_at.isoformat()
        }
    
    async def get_daily_usage(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        days: int = 30
    ) -> List[dict]:
        """获取每日使用统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.date(TokenUsage.created_at).label("date"),
            func.sum(TokenUsage.total_tokens).label("total")
        )
        
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        if tenant_id:
            query = query.where(TokenUsage.tenant_id == tenant_id)
        
        query = query.where(TokenUsage.created_at >= start_date)
        query = query.group_by(func.date(TokenUsage.created_at))
        query = query.order_by(func.date(TokenUsage.created_at))
        
        result = await self.db.execute(query)
        
        return [
            {"date": str(row[0]), "total_tokens": row[1]}
            for row in result.all()
        ]
    
    async def check_user_quota(self, user_id: str, required_tokens: int) -> bool:
        """检查用户配额是否足够"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        available = user.personal_quota - (user.personal_used or 0)
        return available >= required_tokens
    
    async def check_tenant_quota(self, tenant_id: str, required_tokens: int) -> bool:
        """检查租户配额是否足够"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return False
        
        available = tenant.total_quota - (tenant.used_quota or 0)
        return available >= required_tokens
    
    async def reset_user_usage(self, user_id: str):
        """重置用户使用量"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.personal_used = 0
            await self.db.commit()
    
    async def reset_tenant_usage(self, tenant_id: str):
        """重置租户使用量"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.used_quota = 0
            await self.db.commit()
    
    async def get_top_users(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 10,
        days: int = 30
    ) -> List[dict]:
        """获取Token使用量排名前N的用户"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            TokenUsage.user_id,
            func.sum(TokenUsage.total_tokens).label("total")
        ).where(TokenUsage.created_at >= start_date)
        
        if tenant_id:
            query = query.where(TokenUsage.tenant_id == tenant_id)
        
        query = query.group_by(TokenUsage.user_id)
        query = query.order_by(func.sum(TokenUsage.total_tokens).desc())
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        
        top_users = []
        for row in result.all():
            # 获取用户信息
            user_result = await self.db.execute(
                select(User).where(User.id == row[0])
            )
            user = user_result.scalar_one_or_none()
            
            top_users.append({
                "user_id": str(row[0]),
                "username": user.username if user else "Unknown",
                "total_tokens": row[1]
            })
        
        return top_users
    
    async def calculate_cost(
        self,
        total_tokens: int,
        model: str,
        price_per_1k_input: float = 0.01,
        price_per_1k_output: float = 0.03
    ) -> float:
        """计算Token消耗成本（简化实现）"""
        # 简化计算 - 实际应该根据不同模型有不同的价格
        # 假设 input:output = 1:2
        input_tokens = total_tokens // 3
        output_tokens = total_tokens - input_tokens
        
        cost = (input_tokens / 1000) * price_per_1k_input + \
               (output_tokens / 1000) * price_per_1k_output
        
        return round(cost, 4)