"""
E-Claw 任务管理接口
支持多模态任务提交、断点续跑、实时进度更新
"""
import uuid
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.models import User, Task, TaskStatus, TaskPriority, Tenant
from app.services.task_service import TaskService

router = APIRouter()


# ============== 请求/响应模型 ==============

class TaskSubmitRequest(BaseModel):
    name: str
    description: str = ""
    task_type: str = "general"  # general, document_process, data_analysis, etc.
    input_text: str = ""
    priority: str = "medium"  # low, medium, high


class TaskResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    status: str
    priority: str
    task_type: str
    input_text: str = ""
    progress: int = 0
    result: str = ""
    error_message: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    submit_time: str
    start_time: str = ""
    end_time: str = ""
    checkpoint_data: dict = None
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应（包含总数）"""
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskResumeRequest(BaseModel):
    task_id: str


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    task_ids: List[str]


# ============== 任务接口 ==============

@router.post("", response_model=TaskResponse)
async def submit_task(
    name: str = Form(...),
    description: str = Form(""),
    task_type: str = Form("general"),
    input_text: str = Form(""),
    priority: str = Form("medium"),
    files: Optional[List[UploadFile]] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """提交新任务 (US-EMP-001)"""
    # 检查配额
    if current_user.personal_used >= current_user.personal_quota:
        raise HTTPException(
            status_code=403,
            detail="Personal quota exhausted"
        )
    
    # 检查租户配额
    if current_user.tenant_id:
        result = await db.execute(
            select(Tenant).where(Tenant.id == current_user.tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant and tenant.used_quota >= tenant.total_quota:
            raise HTTPException(
                status_code=403,
                detail="Tenant quota exhausted"
            )
    
    # 处理上传的文件
    input_files = []
    if files:
        for file in files:
            content = await file.read()
            # 这里应该保存到文件存储，简化处理
            input_files.append({
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(content)
            })
    
    # 创建任务
    task = Task(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=name,
        description=description,
        task_type=task_type,
        input_text=input_text[:4000],  # 限制输入长度
        input_files=json.dumps(input_files),
        priority=TaskPriority(priority),
        status=TaskStatus.PENDING,
        submit_time=datetime.utcnow()
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # 启动任务执行（异步）
    task_service = TaskService(db)
    await task_service.execute_task_async(str(task.id))
    
    return TaskResponse(
        id=str(task.id),
        name=task.name,
        description=task.description or "",
        status=task.status.value,
        priority=task.priority.value,
        task_type=task.task_type or "",
        input_text=task.input_text or "",
        progress=task.progress,
        result=task.result or "",
        error_message=task.error_message or "",
        input_tokens=task.input_tokens,
        output_tokens=task.output_tokens,
        submit_time=task.submit_time.isoformat()
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(default=None, description="Filter by task status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取任务列表（包含总数）"""
    # 构建查询基础
    base_query = select(Task).where(Task.user_id == current_user.id)
    
    if status:
        base_query = base_query.where(Task.status == TaskStatus(status))
    
    # 获取总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    paginated_query = base_query.order_by(Task.submit_time.desc())
    paginated_query = paginated_query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(paginated_query)
    tasks = result.scalars().all()
    
    items = [
        TaskResponse(
            id=str(t.id),
            name=t.name,
            description=t.description or "",
            status=t.status.value,
            priority=t.priority.value,
            task_type=t.task_type or "",
            input_text=t.input_text or "",
            progress=t.progress,
            result=t.result or "",
            error_message=t.error_message or "",
            input_tokens=t.input_tokens,
            output_tokens=t.output_tokens,
            submit_time=t.submit_time.isoformat(),
            start_time=t.start_time.isoformat() if t.start_time else "",
            end_time=t.end_time.isoformat() if t.end_time else "",
            checkpoint_data=json.loads(t.checkpoint_data) if t.checkpoint_data else None
        )
        for t in tasks
    ]
    
    return TaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取任务详情"""
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        id=str(task.id),
        name=task.name,
        description=task.description or "",
        status=task.status.value,
        priority=task.priority.value,
        task_type=task.task_type or "",
        input_text=task.input_text or "",
        progress=task.progress,
        result=task.result or "",
        error_message=task.error_message or "",
        input_tokens=task.input_tokens,
        output_tokens=task.output_tokens,
        submit_time=task.submit_time.isoformat(),
        start_time=task.start_time.isoformat() if task.start_time else "",
        end_time=task.end_time.isoformat() if task.end_time else ""
    )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """取消任务"""
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail="Task cannot be cancelled"
        )
    
    task.status = TaskStatus.CANCELLED
    task.end_time = datetime.utcnow()
    await db.commit()
    
    return {"message": f"Task {task_id} cancelled"}


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """恢复任务（断点续跑）(US-EMP-001)"""
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查是否有断点数据
    if not task.checkpoint_data:
        raise HTTPException(
            status_code=400,
            detail="No checkpoint data available"
        )
    
    # 更新任务状态
    task.status = TaskStatus.PENDING
    task.progress = task.checkpoint_data.get("progress", 0)
    
    # 重新执行
    task_service = TaskService(db)
    await task_service.execute_task_async(task_id, resume_from_checkpoint=True)
    
    return {"message": f"Task {task_id} resumed from checkpoint"}


@router.get("/{task_id}/checkpoint")
async def get_checkpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取任务断点数据"""
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "progress": task.progress,
        "checkpoint_data": task.checkpoint_data,
        "last_checkpoint_at": task.last_checkpoint_at.isoformat() if task.last_checkpoint_at else None
    }

# ============== 批量操作接口 ==============

@router.post("/batch/cancel")
async def batch_cancel_tasks(
    request: BatchOperationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """批量取消任务"""
    if not request.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")
    
    # 查询用户的所有指定任务
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id.in_(request.task_ids),
                Task.user_id == current_user.id
            )
        )
    )
    tasks = result.scalars().all()
    
    cancelled_count = 0
    for task in tasks:
        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.end_time = datetime.utcnow()
            cancelled_count += 1
    
    await db.commit()
    
    return {
        "message": f"Batch cancel completed",
        "cancelled_count": cancelled_count,
        "total_requested": len(request.task_ids)
    }


@router.post("/batch/delete")
async def batch_delete_tasks(
    request: BatchOperationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """批量删除任务"""
    if not request.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")
    
    # 查询用户的所有指定任务
    result = await db.execute(
        select(Task).where(
            and_(
                Task.id.in_(request.task_ids),
                Task.user_id == current_user.id
            )
        )
    )
    tasks = result.scalars().all()
    
    deleted_count = 0
    for task in tasks:
        # 只能删除已完成、失败或已取消的任务
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            await db.delete(task)
            deleted_count += 1
    
    await db.commit()
    
    return {
        "message": f"Batch delete completed",
        "deleted_count": deleted_count,
        "total_requested": len(request.task_ids)
    }
