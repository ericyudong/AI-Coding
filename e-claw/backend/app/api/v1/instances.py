"""
E-Claw 实例管理接口
提供OpenCLAW实例的创建、启动、停止、删除等REST API
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.models import User
from app.services.instance_service import (
    InstanceService,
    CreateInstanceRequest,
    create_default_quota
)
from app.services.system_image_service import SystemImageService, get_all_default_templates

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 确保日志输出到控制台
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


router = APIRouter(prefix="", tags=["instances"])


# ============== 请求/响应模型 ==============

class InstanceCreateRequest(BaseModel):
    """创建实例请求"""
    name: str = Field(..., min_length=3, max_length=50, description="实例名称")
    description: Optional[str] = Field(None, description="实例描述")
    instance_type: str = Field("openclaw", description="实例类型: openclaw, ubuntu, webtop, debian, centos, custom")
    cpu_cores: int = Field(2, ge=1, le=32, description="CPU核心数")
    memory_gb: int = Field(4, ge=1, le=128, description="内存大小(GB)")
    disk_gb: int = Field(20, ge=10, le=1000, description="磁盘大小(GB)")
    gpu_enabled: bool = Field(False, description="是否启用GPU")
    gpu_count: int = Field(0, ge=0, le=4, description="GPU数量")
    os_type: str = Field("linux", description="操作系统类型")
    os_version: str = Field("latest", description="操作系统版本")
    image_registry: Optional[str] = Field(None, description="自定义镜像仓库")
    image_tag: Optional[str] = Field(None, description="自定义镜像标签")
    storage_class: str = Field("", description="存储类")


class InstanceUpdateRequest(BaseModel):
    """更新实例请求"""
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = None


class InstanceResponse(BaseModel):
    """实例响应"""
    id: str
    name: str
    description: Optional[str]
    status: str
    instance_type: str
    pod_name: Optional[str] = None
    pod_namespace: Optional[str] = None
    docker_url: Optional[str] = None
    docker_port: Optional[int] = None
    access_token: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None


class InstanceListResponse(BaseModel):
    """实例列表响应"""
    items: List[InstanceResponse]
    total: int
    page: int
    page_size: int


class ImageTemplateResponse(BaseModel):
    """镜像模板响应"""
    id: str
    name: str
    description: str
    image: str
    default_port: int
    is_enabled: bool
    env_vars: dict


# ============== 镜像模板接口 ==============

@router.get("/image-templates", response_model=List[ImageTemplateResponse])
async def get_image_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取可用的镜像模板"""
    # 从数据库获取配置
    image_service = SystemImageService(db)
    db_images = await image_service.list_images()
    
    # 合并默认模板和数据库配置
    templates = []
    default_templates = get_all_default_templates()
    
    # 创建数据库配置映射
    db_images_map = {img["instance_type"]: img for img in db_images}
    
    for template in default_templates:
        db_config = db_images_map.get(template["id"], {})
        
        templates.append(ImageTemplateResponse(
            id=template["id"],
            name=template["name"],
            description=template["description"],
            image=db_config.get("image") or template["image"],
            default_port=template["default_port"],
            is_enabled=db_config.get("is_enabled", template["is_enabled"]),
            env_vars=template.get("env_vars", {})
        ))
    
    return templates


@router.post("/image-templates")
async def save_image_template(
    instance_type: str,
    image: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """保存镜像模板配置（仅管理员）"""
    # 检查管理员权限
    from app.models import UserRole
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    image_service = SystemImageService(db)
    
    try:
        result = await image_service.save_image(
            instance_type=instance_type,
            image=image,
            display_name=display_name,
            description=description
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/image-templates/{instance_type}")
async def delete_image_template(
    instance_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除（禁用）镜像模板（仅管理员）"""
    # 检查管理员权限
    from app.models import UserRole
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    image_service = SystemImageService(db)
    
    try:
        result = await image_service.delete_image(instance_type)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== 实例接口 ==============

@router.post("", response_model=InstanceResponse, status_code=201)
async def create_instance(
    request: InstanceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """
    创建新实例 (US-EMP-001)
    
    支持创建多种类型的实例:
    - openclaw: OpenCLAW工作环境
    - ubuntu: Ubuntu桌面环境
    - webtop: Webtop桌面环境
    - debian: Debian桌面环境
    - centos: CentOS桌面环境
    - custom: 自定义镜像
    """
    # 检查并创建用户配额（如果不存在）
    from app.models import UserQuota
    from sqlalchemy import select
    
    result = await db.execute(
        select(UserQuota).where(UserQuota.user_id == str(current_user.id))
    )
    quota = result.scalar_one_or_none()
    
    if not quota:
        quota = await create_default_quota(db, str(current_user.id))
    
    # 创建实例服务
    instance_service = InstanceService(db)
    
    # 构建请求
    create_req = CreateInstanceRequest(
        name=request.name,
        description=request.description,
        instance_type=request.instance_type,
        cpu_cores=request.cpu_cores,
        memory_gb=request.memory_gb,
        disk_gb=request.disk_gb,
        gpu_enabled=request.gpu_enabled,
        gpu_count=request.gpu_count,
        os_type=request.os_type,
        os_version=request.os_version,
        image_registry=request.image_registry,
        image_tag=request.image_tag,
        storage_class=request.storage_class
    )
    
    try:
        result = await instance_service.create_instance(
            user_id=str(current_user.id),
            req=create_req
        )
        
        return InstanceResponse(
            id=result["instance_id"],
            name=result["instance_name"],
            description=request.description,
            status=result["status"],
            instance_type=result["instance_type"],
            pod_name=result.get("pod_name"),
            pod_namespace=result.get("pod_namespace"),
            docker_url=result.get("service_url"),
            docker_port=result.get("port"),
            access_token=result.get("access_token"),
            created_at=result.get("created_at")
        )
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Create instance validation error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to create instance: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("", response_model=InstanceListResponse)
async def list_instances(
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取用户实例列表"""
    instance_service = InstanceService(db)
    
    offset = (page - 1) * page_size
    instances, total = await instance_service.list_instances(
        user_id=str(current_user.id),
        status=status,
        offset=offset,
        limit=page_size
    )
    
    items = [
        InstanceResponse(
            id=inst["id"],
            name=inst["name"],
            description=inst.get("description"),
            status=inst["status"],
            instance_type=inst.get("instance_type", "openclaw"),
            pod_name=inst.get("pod_name"),
            docker_url=inst.get("docker_url"),
            docker_port=inst.get("docker_port"),
            created_at=inst.get("created_at")
        )
        for inst in instances
    ]
    
    return InstanceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取实例详情"""
    instance_service = InstanceService(db)
    
    instance = await instance_service.get_instance(instance_id, str(current_user.id))
    
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    return InstanceResponse(
        id=instance["id"],
        name=instance["name"],
        description=instance.get("description"),
        status=instance["status"],
        instance_type=instance.get("instance_type", "openclaw"),
        pod_name=instance.get("pod_name"),
        pod_namespace=instance.get("pod_namespace"),
        docker_url=instance.get("docker_url"),
        docker_port=instance.get("docker_port"),
        created_at=instance.get("created_at"),
        started_at=instance.get("started_at")
    )


@router.post("/{instance_id}/start")
async def start_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """启动实例"""
    instance_service = InstanceService(db)
    
    try:
        result = await instance_service.start_instance(instance_id, str(current_user.id))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/stop")
async def stop_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """停止实例"""
    instance_service = InstanceService(db)
    
    try:
        result = await instance_service.stop_instance(instance_id, str(current_user.id))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}")
async def delete_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除实例"""
    instance_service = InstanceService(db)
    
    try:
        result = await instance_service.delete_instance(instance_id, str(current_user.id))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
