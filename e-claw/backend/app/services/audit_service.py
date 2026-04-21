"""
E-Claw 审计日志服务
全链路操作记录
"""
import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.models import AuditLog


class AuditService:
    """审计日志服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        action: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_body: Optional[dict] = None,
        response_status: Optional[int] = None
    ) -> AuditLog:
        """记录操作日志"""
        audit_log = AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            method=method,
            path=path,
            ip_address=ip_address,
            user_agent=user_agent,
            request_body=request_body,
            response_status=response_status
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)
        return audit_log
    
    async def log_login(self, user_id: str, tenant_id: Optional[str], ip_address: str):
        """记录登录"""
        await self.log_action(
            action="user_login",
            user_id=user_id,
            tenant_id=tenant_id,
            response_status=200,
            ip_address=ip_address
        )
    
    async def log_logout(self, user_id: str, tenant_id: Optional[str], ip_address: str):
        """记录登出"""
        await self.log_action(
            action="user_logout",
            user_id=user_id,
            tenant_id=tenant_id,
            response_status=200,
            ip_address=ip_address
        )
    
    async def log_task_created(
        self,
        user_id: str,
        tenant_id: Optional[str],
        task_id: str,
        ip_address: Optional[str] = None
    ):
        """记录任务创建"""
        await self.log_action(
            action="task_created",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="task",
            resource_id=task_id,
            ip_address=ip_address,
            response_status=201
        )
    
    async def log_task_completed(
        self,
        user_id: str,
        tenant_id: Optional[str],
        task_id: str,
        ip_address: Optional[str] = None
    ):
        """记录任务完成"""
        await self.log_action(
            action="task_completed",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="task",
            resource_id=task_id,
            ip_address=ip_address,
            response_status=200
        )
    
    async def log_knowledge_base_created(
        self,
        user_id: str,
        tenant_id: Optional[str],
        kb_id: str,
        ip_address: Optional[str] = None
    ):
        """记录知识库创建"""
        await self.log_action(
            action="knowledge_base_created",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="knowledge_base",
            resource_id=kb_id,
            ip_address=ip_address,
            response_status=201
        )
    
    async def log_document_uploaded(
        self,
        user_id: str,
        tenant_id: Optional[str],
        document_id: str,
        ip_address: Optional[str] = None
    ):
        """记录文档上传"""
        await self.log_action(
            action="document_uploaded",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="document",
            resource_id=document_id,
            ip_address=ip_address,
            response_status=201
        )
    
    async def query_logs(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> List[AuditLog]:
        """查询日志"""
        query = select(AuditLog)
        
        if tenant_id:
            query = query.where(AuditLog.tenant_id == tenant_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action.like(f"%{action}%"))
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)
        
        query = query.order_by(desc(AuditLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_user_activities(
        self,
        user_id: str,
        days: int = 7,
        limit: int = 100
    ) -> List[AuditLog]:
        """获取用户活动记录"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(AuditLog).where(
            and_(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= start_date
            )
        )
        query = query.order_by(desc(AuditLog.created_at))
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50
    ) -> List[AuditLog]:
        """获取资源操作历史"""
        query = select(AuditLog).where(
            and_(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id
            )
        )
        query = query.order_by(desc(AuditLog.created_at))
        query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_tenant_activity_summary(
        self,
        tenant_id: str,
        days: int = 30
    ) -> dict:
        """获取租户活动摘要"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 总操作数
        total_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.created_at >= start_date
                )
            )
        )
        total_actions = total_result.scalar() or 0
        
        # 按操作类型统计
        action_counts = {}
        actions_result = await self.db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.created_at >= start_date
                )
            )
            .group_by(AuditLog.action)
        )
        for action, count in actions_result.all():
            action_counts[action] = count
        
        # 活跃用户数
        active_users_result = await self.db.execute(
            select(func.count(func.distinct(AuditLog.user_id)))
            .where(
                and_(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.created_at >= start_date
                )
            )
        )
        active_users = active_users_result.scalar() or 0
        
        return {
            "tenant_id": tenant_id,
            "period_days": days,
            "total_actions": total_actions,
            "action_counts": action_counts,
            "active_users": active_users
        }
    
    async def delete_old_logs(self, days: int = 365):
        """删除旧日志"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 只删除已归档的日志
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.created_at < cutoff_date)
        )
        logs = result.scalars().all()
        
        for log in logs:
            await self.db.delete(log)
        
        await self.db.commit()
        return len(logs)