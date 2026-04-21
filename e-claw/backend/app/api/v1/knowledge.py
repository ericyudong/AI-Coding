"""
E-Claw 知识库管理接口
支持个人知识库和部门共享知识库
"""
import uuid
import json
import os
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.core.config import settings
from app.models import User, UserRole, KnowledgeBase, Document, Tenant

router = APIRouter()

# Lazy import to avoid potential import errors
def get_knowledge_service(db):
    from app.services.knowledge_service import KnowledgeService
    return KnowledgeService(db)


# ============== 请求/响应模型 ==============

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str = ""
    kb_type: str = "personal"  # personal, dept_shared


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str
    owner_id: str
    tenant_id: str
    status: str
    review_status: str
    doc_count: int
    total_size: int
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应（包含总数）"""
    items: List[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: str
    
    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    knowledge_base_id: Optional[str] = None
    top_k: int = 5


class SearchResult(BaseModel):
    document_id: str
    filename: str
    content: str
    score: float


# ============== 知识库接口 ==============

@router.get("")
async def list_knowledge_bases(
    kb_type: Optional[str] = Query(default=None, description="Knowledge base type: personal, dept_shared"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取知识库列表"""
    # 构建查询
    query = select(KnowledgeBase)
    
    # 根据用户角色过滤
    if current_user.role == UserRole.EMPLOYEE:
        # 普通员工只能看到自己的个人知识库
        query = query.where(
            and_(
                KnowledgeBase.owner_id == current_user.id,
                KnowledgeBase.type == "personal"
            )
        )
    elif current_user.role == UserRole.DEPT_ADMIN:
        # 部门管理员可以看到自己的个人知识库和部门共享知识库
        query = query.where(
            or_(
                KnowledgeBase.owner_id == current_user.id,
                and_(
                    KnowledgeBase.tenant_id == current_user.tenant_id,
                    KnowledgeBase.type == "dept_shared"
                )
            )
        )
    # 超级管理员可以看到所有
    
    # 过滤类型
    if kb_type:
        query = query.where(KnowledgeBase.type == kb_type)
    
    # 分页
    query = query.order_by(KnowledgeBase.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    knowledge_bases = result.scalars().all()
    
    return [
        KnowledgeBaseResponse(
            id=str(kb.id),
            name=kb.name,
            description=kb.description or "",
            type=kb.type or "",
            owner_id=str(kb.owner_id),
            tenant_id=str(kb.tenant_id) if kb.tenant_id else "",
            status=kb.status or "",
            review_status=kb.review_status or "",
            doc_count=kb.doc_count or 0,
            total_size=kb.total_size or 0,
            created_at=kb.created_at.isoformat(),
            updated_at=kb.updated_at.isoformat()
        )
        for kb in knowledge_bases
    ]


@router.post("")
async def create_knowledge_base(
    request: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """创建知识库"""
    print(f"DEBUG: Creating knowledge base with name={request.name}, kb_type={request.kb_type}")
    # 个人知识库可以任何人创建
    # 部门共享知识库需要部门管理员或超级管理员
    
    if request.kb_type == "dept_shared":
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
            raise HTTPException(
                status_code=403,
                detail="Only dept admin or super admin can create dept shared knowledge base"
            )
        
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Dept admin must belong to a tenant"
            )
    
    # 创建知识库
    knowledge_base = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        owner_id=current_user.id,
        name=request.name,
        description=request.description,
        type=request.kb_type,
        status="active",
        review_status="approved" if request.kb_type == "personal" else "pending"
    )
    
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    
    return KnowledgeBaseResponse(
        id=str(knowledge_base.id),
        name=knowledge_base.name,
        description=knowledge_base.description or "",
        type=knowledge_base.type or "",
        owner_id=str(knowledge_base.owner_id),
        tenant_id=str(knowledge_base.tenant_id) if knowledge_base.tenant_id else "",
        status=knowledge_base.status or "",
        review_status=knowledge_base.review_status or "",
        doc_count=knowledge_base.doc_count or 0,
        total_size=knowledge_base.total_size or 0,
        created_at=knowledge_base.created_at.isoformat(),
        updated_at=knowledge_base.updated_at.isoformat()
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取知识库详情"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查
    if not _can_access_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to access this knowledge base"
        )
    
    return KnowledgeBaseResponse(
        id=str(kb.id),
        name=kb.name,
        description=kb.description or "",
        type=kb.type or "",
        owner_id=str(kb.owner_id),
        tenant_id=str(kb.tenant_id) if kb.tenant_id else "",
        status=kb.status or "",
        review_status=kb.review_status or "",
        doc_count=kb.doc_count or 0,
        total_size=kb.total_size or 0,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat()
    )


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: str,
    request: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查 - 只有所有者或管理员可以更新
    if not _can_modify_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to modify this knowledge base"
        )
    
    if request.name is not None:
        kb.name = request.name
    if request.description is not None:
        kb.description = request.description
    
    kb.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(kb)
    
    return KnowledgeBaseResponse(
        id=str(kb.id),
        name=kb.name,
        description=kb.description or "",
        type=kb.type or "",
        owner_id=str(kb.owner_id),
        tenant_id=str(kb.tenant_id) if kb.tenant_id else "",
        status=kb.status or "",
        review_status=kb.review_status or "",
        doc_count=kb.doc_count or 0,
        total_size=kb.total_size or 0,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat()
    )


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查
    if not _can_modify_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to delete this knowledge base"
        )
    
    # 软删除
    kb.status = "deleted"
    kb.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Knowledge base deleted successfully"}


# ============== 文档接口 ==============

@router.get("/{kb_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    kb_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取知识库文档列表"""
    # 检查知识库
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查
    if not _can_access_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to access this knowledge base"
        )
    
    # 获取文档列表
    query = select(Document).where(Document.knowledge_base_id == kb_id)
    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return [
        DocumentResponse(
            id=str(d.id),
            knowledge_base_id=str(d.knowledge_base_id),
            filename=d.filename,
            file_type=d.file_type or "",
            file_size=d.file_size or 0,
            status=d.status or "",
            chunk_count=d.chunk_count or 0,
            created_at=d.created_at.isoformat()
        )
        for d in documents
    ]


@router.post("/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """上传文档到知识库"""
    # 检查知识库
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查
    if not _can_modify_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to upload to this knowledge base"
        )
    
    # 检查审核状态
    if kb.review_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Knowledge base is under review"
        )
    
    # 读取文件内容
    content = await file.read()
    file_size = len(content)
    
    # 检查文件大小
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE} bytes"
        )
    
    # 检查租户存储配额
    if kb.tenant_id:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == kb.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            # 简单检查总大小
            kb.total_size = (kb.total_size or 0) + file_size
    
    # 保存文件
    file_path = await _save_file(kb_id, file.filename, content)
    
    # 创建文档记录
    document = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_id,
        filename=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        status="pending",
        chunk_count=0
    )
    db.add(document)
    
    # 更新知识库统计
    kb.doc_count = (kb.doc_count or 0) + 1
    kb.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(document)
    
    # 异步处理文档向量化
    knowledge_service = KnowledgeService(db)
    await knowledge_service.process_document_async(str(document.id))
    
    return {
        "message": "Document uploaded successfully",
        "document_id": str(document.id)
    }


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除文档"""
    # 检查知识库
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    
    # 权限检查
    if not _can_modify_knowledge_base(current_user, kb):
        raise HTTPException(
            status_code=403,
            detail="No permission to delete from this knowledge base"
        )
    
    # 检查文档
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == doc_id,
                Document.knowledge_base_id == kb_id
            )
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 软删除
    document.status = "deleted"
    
    # 更新知识库统计
    kb.doc_count = max(0, (kb.doc_count or 1) - 1)
    kb.total_size = max(0, (kb.total_size or 0) - (document.file_size or 0))
    kb.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Document deleted successfully"}


# ============== 搜索接口 ==============

@router.post("/search", response_model=List[SearchResult])
async def search_knowledge(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """搜索知识库"""
    knowledge_service = KnowledgeService(db)
    
    # 获取可访问的知识库
    accessible_kbs = await _get_accessible_knowledge_bases(current_user, db)
    
    if not accessible_kbs:
        return []
    
    # 如果指定了知识库ID，检查权限
    if request.knowledge_base_id:
        if request.knowledge_base_id not in accessible_kbs:
            raise HTTPException(
                status_code=403,
                detail="No permission to search this knowledge base"
            )
        kb_ids = [request.knowledge_base_id]
    else:
        kb_ids = accessible_kbs
    
    # 执行搜索
    results = await knowledge_service.search(
        query=request.query,
        kb_ids=kb_ids,
        top_k=request.top_k
    )
    
    return [
        SearchResult(
            document_id=str(r["document_id"]),
            filename=r["filename"],
            content=r["content"],
            score=r["score"]
        )
        for r in results
    ]


# ============== 辅助函数 ==============

def _can_access_knowledge_base(user: User, kb: KnowledgeBase) -> bool:
    """检查用户是否可以访问知识库"""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    # 所有者可以访问
    if kb.owner_id == user.id:
        return True
    
    # 部门共享知识库，本部门用户可以访问
    if kb.type == "dept_shared" and kb.tenant_id == user.tenant_id:
        return True
    
    return False


def _can_modify_knowledge_base(user: User, kb: KnowledgeBase) -> bool:
    """检查用户是否可以修改知识库"""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    # 所有者可以修改
    if kb.owner_id == user.id:
        return True
    
    # 部门管理员可以修改本部门共享知识库
    if kb.type == "dept_shared" and user.role == UserRole.DEPT_ADMIN:
        if kb.tenant_id == user.tenant_id:
            return True
    
    return False


async def _get_accessible_knowledge_bases(user: User, db: AsyncSession) -> List[str]:
    """获取用户可访问的知识库ID列表"""
    query = select(KnowledgeBase.id).where(KnowledgeBase.status != "deleted")
    
    if user.role == UserRole.EMPLOYEE:
        query = query.where(KnowledgeBase.owner_id == user.id)
    elif user.role == UserRole.DEPT_ADMIN and user.tenant_id:
        query = query.where(
            or_(
                KnowledgeBase.owner_id == user.id,
                and_(
                    KnowledgeBase.tenant_id == user.tenant_id,
                    KnowledgeBase.type == "dept_shared"
                )
            )
        )
    
    result = await db.execute(query)
    return [str(row[0]) for row in result.all()]


async def _save_file(kb_id: str, filename: str, content: bytes) -> str:
    """保存文件到存储"""
    # 创建目录
    base_dir = os.path.join(settings.KNOWLEDGE_BASE_DIR, kb_id)
    os.makedirs(base_dir, exist_ok=True)
    
    # 生成唯一文件名
    import uuid as uuid_module
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid_module.uuid4()}{ext}"
    file_path = os.path.join(base_dir, unique_filename)
    
    # 写入文件
    with open(file_path, "wb") as f:
        f.write(content)
    
    return file_path