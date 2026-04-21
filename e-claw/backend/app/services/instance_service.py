"""
E-Claw 实例服务
处理OpenCLAW实例的创建、启动、停止、删除等操作
参考ClawManager的InstanceService实现
"""
import os
import uuid
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import User, UserQuota, Task, TaskStatus


# 请求模型
@dataclass
class CreateInstanceRequest:
    """创建实例请求"""
    name: str
    description: Optional[str] = None
    instance_type: str = "openclaw"  # openclaw, ubuntu, webtop, debian, centos, custom
    cpu_cores: int = 2
    memory_gb: int = 4
    disk_gb: int = 20
    gpu_enabled: bool = False
    gpu_count: int = 0
    os_type: str = "linux"
    os_version: str = "latest"
    image_registry: Optional[str] = None
    image_tag: Optional[str] = None
    storage_class: str = ""


@dataclass
class UpdateInstanceRequest:
    """更新实例请求"""
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class InstanceStatus:
    """实例状态"""
    instance_id: str
    status: str
    pod_name: Optional[str] = None
    pod_namespace: Optional[str] = None
    pod_ip: Optional[str] = None
    pod_status: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None


class InstanceService:
    """实例服务 - 处理OpenCLAW实例的生命周期管理"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_instance(
        self,
        user_id: str,
        req: CreateInstanceRequest
    ) -> Dict[str, Any]:
        """
        创建新实例
        
        流程:
        1. 检查用户配额
        2. 验证实例名称唯一性
        3. 清理孤儿资源
        4. 创建数据库记录
        5. 创建PVC存储
        6. 创建Pod
        7. 创建Service
        8. 更新数据库状态并广播
        """
        from app.services import k8s_service
        from app.services.instance_runtime import (
            build_runtime_config,
            with_instance_proxy_env,
            get_cpu_memory_config
        )
        
        # 1. 获取用户配额
        quota = await self._get_user_quota(user_id)
        if not quota:
            raise ValueError("User quota not found. Please contact administrator.")
        
        # 2. 检查实例数量限制
        current_count = await self._count_user_instances(user_id)
        if current_count >= quota.max_instances:
            raise ValueError(f"Instance limit reached: {current_count}/{quota.max_instances}")
        
        # 3. 计算当前资源使用
        current_resources = await self._get_user_current_resources(user_id)
        
        # 4. 检查CPU配额
        if current_resources["cpu"] + req.cpu_cores > quota.max_cpu_cores:
            raise ValueError(
                f"CPU cores exceed quota: current {current_resources['cpu']}, "
                f"requested {req.cpu_cores}, max {quota.max_cpu_cores}"
            )
        
        # 5. 检查内存配额
        if current_resources["memory"] + req.memory_gb > quota.max_memory_gb:
            raise ValueError(
                f"Memory exceed quota: current {current_resources['memory']}GB, "
                f"requested {req.memory_gb}GB, max {quota.max_memory_gb}GB"
            )
        
        # 6. 检查存储配额
        if current_resources["storage"] + req.disk_gb > quota.max_storage_gb:
            raise ValueError(
                f"Storage exceed quota: current {current_resources['storage']}GB, "
                f"requested {req.disk_gb}GB, max {quota.max_storage_gb}GB"
            )
        
        # 7. 检查GPU配额
        requested_gpu = req.gpu_count if req.gpu_enabled else 0
        if current_resources["gpu"] + requested_gpu > quota.max_gpu_count:
            raise ValueError(
                f"GPU count exceed quota: current {current_resources['gpu']}, "
                f"requested {requested_gpu}, max {quota.max_gpu_count}"
            )
        
        # 8. 检查实例名称唯一性
        name_exists = await self._instance_name_exists(user_id, req.name)
        if name_exists:
            raise ValueError("Instance name already exists")
        
        # 9. 获取运行时配置
        runtime_config = build_runtime_config(
            instance_type=req.instance_type,
            os_type=req.os_type,
            os_version=req.os_version,
            custom_registry=req.image_registry,
            custom_tag=req.image_tag
        )
        
        # 如果没有指定镜像，使用默认配置
        if not req.image_registry and not req.image_tag:
            from app.services.system_image_service import get_default_image_template
            default_template = get_default_image_template(req.instance_type)
            if default_template:
                runtime_config.image = default_template["image"]
        
        # 10. 生成访问令牌
        access_token = self._generate_access_token()
        
        # 11. 构建环境变量（包含Gateway配置）
        gateway_env = self._build_gateway_env(access_token, req.instance_type)
        merged_env = with_instance_proxy_env(
            req.instance_type,
            0,  # instance_id稍后更新
            {**runtime_config.env, **gateway_env}
        )
        
        # 12. 准备资源名称
        instance_id = str(uuid.uuid4())
        resource_name = f"eclaw-{req.instance_type}-{instance_id[:8]}"
        
        # 13. 在K8s中创建资源
        try:
            # 创建PVC
            pvc_result = await k8s_service.create_pvc(
                resource_name=resource_name,
                storage_size_gb=req.disk_gb,
                storage_class=req.storage_class
            )
            if "error" in pvc_result:
                raise Exception(f"Failed to create PVC: {pvc_result['error']}")
            
            # 创建Pod
            resources = get_cpu_memory_config(
                req.cpu_cores,
                req.memory_gb,
                req.gpu_enabled,
                req.gpu_count
            )
            
            pod_result = await k8s_service.create_pod(
                resource_name=resource_name,
                image=runtime_config.image,
                port=runtime_config.port,
                mount_path=runtime_config.mount_path,
                env_vars=merged_env,
                resources=resources,
                user_id=user_id,
                instance_id=instance_id
            )
            if "error" in pod_result:
                raise Exception(f"Failed to create pod: {pod_result['error']}")
            
            # 创建Service
            service_result = await k8s_service.create_service(
                resource_name=resource_name,
                port=runtime_config.port
            )
            if "error" in service_result:
                # Service失败不影响实例创建，继续
                pass
            
        except Exception as e:
            # 清理已创建的资源
            await k8s_service.cleanup_resources(resource_name)
            raise Exception(f"Failed to create instance: {str(e)}")
        
        # 14. 创建任务记录（作为实例的关联）
        task = Task(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            name=req.name,
            description=req.description,
            task_type=f"instance_{req.instance_type}",
            status=TaskStatus.RUNNING,
            docker_container_id=resource_name,
            docker_container_name=resource_name,
            docker_status="running",
            docker_url=f"http://localhost:{runtime_config.port}",
            docker_port=runtime_config.port,
            docker_image_template=req.instance_type,
            docker_created_at=datetime.utcnow(),
            submit_time=datetime.utcnow(),
            start_time=datetime.utcnow()
        )
        self.db.add(task)
        
        # 15. 更新任务的环境变量信息（存储访问令牌）
        task.input_text = access_token  # 临时存储token
        
        await self.db.commit()
        await self.db.refresh(task)
        
        return {
            "instance_id": str(task.id),
            "instance_name": task.name,
            "instance_type": req.instance_type,
            "status": "creating",
            "pod_name": resource_name,
            "pod_namespace": k8s_service.NAMESPACE,
            "service_url": f"http://localhost:{runtime_config.port}",
            "port": runtime_config.port,
            "access_token": access_token,
            "created_at": task.submit_time.isoformat()
        }
    
    async def get_instance(self, instance_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取实例详情"""
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.id == instance_id,
                    Task.user_id == user_id
                )
            )
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return None
        
        return {
            "id": str(task.id),
            "name": task.name,
            "description": task.description,
            "status": task.status.value if task.status else task.docker_status,
            "instance_type": task.docker_image_template,
            "pod_name": task.docker_container_name,
            "pod_namespace": None,
            "docker_url": task.docker_url,
            "docker_port": task.docker_port,
            "created_at": task.submit_time.isoformat() if task.submit_time else None,
            "started_at": task.start_time.isoformat() if task.start_time else None
        }
    
    async def list_instances(
        self,
        user_id: str,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> tuple[List[Dict[str, Any]], int]:
        """获取用户实例列表"""
        # 构建查询
        query = select(Task).where(Task.user_id == user_id)
        
        if status:
            query = query.where(Task.status == TaskStatus(status))
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        query = query.order_by(Task.submit_time.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        tasks = result.scalars().all()
        
        instances = []
        for task in tasks:
            instances.append({
                "id": str(task.id),
                "name": task.name,
                "description": task.description,
                "status": task.status.value if task.status else task.docker_status,
                "instance_type": task.docker_image_template,
                "docker_url": task.docker_url,
                "docker_port": task.docker_port,
                "created_at": task.submit_time.isoformat() if task.submit_time else None
            })
        
        return instances, total
    
    async def start_instance(self, instance_id: str, user_id: str) -> Dict[str, Any]:
        """启动实例"""
        from app.services import k8s_service
        
        instance = await self.get_instance(instance_id, user_id)
        if not instance:
            raise ValueError("Instance not found")
        
        if instance["status"] == "running":
            raise ValueError("Instance is already running")
        
        # 启动Pod
        result = await k8s_service.start_environment(instance["pod_name"])
        
        if "error" in result:
            raise Exception(result["error"])
        
        # 更新数据库状态
        task = await self._get_task_by_id(instance_id)
        if task:
            task.status = TaskStatus.RUNNING
            task.start_time = datetime.utcnow()
            await self.db.commit()
        
        return {
            "status": "running",
            "message": "Instance started successfully"
        }
    
    async def stop_instance(self, instance_id: str, user_id: str) -> Dict[str, Any]:
        """停止实例"""
        from app.services import k8s_service
        
        instance = await self.get_instance(instance_id, user_id)
        if not instance:
            raise ValueError("Instance not found")
        
        if instance["status"] != "running":
            raise ValueError("Instance is not running")
        
        # 停止Pod
        result = await k8s_service.stop_environment(instance["pod_name"])
        
        if "error" in result:
            raise Exception(result["error"])
        
        # 更新数据库状态
        task = await self._get_task_by_id(instance_id)
        if task:
            task.status = TaskStatus.PENDING
            await self.db.commit()
        
        return {
            "status": "stopped",
            "message": "Instance stopped successfully"
        }
    
    async def delete_instance(self, instance_id: str, user_id: str) -> Dict[str, Any]:
        """删除实例"""
        from app.services import k8s_service
        
        instance = await self.get_instance(instance_id, user_id)
        if not instance:
            raise ValueError("Instance not found")
        
        # 删除K8s资源
        await k8s_service.remove_environment(instance["pod_name"])
        
        # 删除数据库记录
        task = await self._get_task_by_id(instance_id)
        if task:
            await self.db.delete(task)
            await self.db.commit()
        
        return {
            "status": "deleted",
            "message": "Instance deleted successfully"
        }
    
    async def get_instance_status(self, instance_id: str, user_id: str) -> InstanceStatus:
        """获取实例详细状态"""
        from app.services import k8s_service
        
        instance = await self.get_instance(instance_id, user_id)
        if not instance:
            raise ValueError("Instance not found")
        
        # 获取K8s pod状态
        pod_status = await k8s_service.get_environment_status(instance["pod_name"])
        
        return InstanceStatus(
            instance_id=instance_id,
            status=instance["status"],
            pod_name=instance.get("pod_name"),
            pod_namespace=instance.get("pod_namespace"),
            pod_status=pod_status,
            created_at=datetime.fromisoformat(instance["created_at"]) if instance.get("created_at") else None
        )
    
    # ==================== 辅助方法 ====================
    
    async def _get_user_quota(self, user_id: str) -> Optional[UserQuota]:
        """获取用户配额"""
        result = await self.db.execute(
            select(UserQuota).where(UserQuota.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _count_user_instances(self, user_id: str) -> int:
        """统计用户当前实例数"""
        result = await self.db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING])
                )
            )
        )
        return result.scalar() or 0
    
    async def _get_user_current_resources(self, user_id: str) -> Dict[str, int]:
        """获取用户当前资源使用"""
        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.status == TaskStatus.RUNNING
                )
            )
        )
        tasks = result.scalars().all()
        
        cpu = 0
        memory = 0
        storage = 0
        gpu = 0
        
        # 从任务中提取资源信息（这里简化为固定值，实际应从Task扩展字段获取）
        for task in tasks:
            cpu += 2  # 默认2核
            memory += 4  # 默认4GB
            storage += 20  # 默认20GB
        
        return {
            "cpu": cpu,
            "memory": memory,
            "storage": storage,
            "gpu": gpu
        }
    
    async def _instance_name_exists(self, user_id: str, name: str) -> bool:
        """检查实例名称是否已存在"""
        result = await self.db.execute(
            select(func.count()).select_from(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.name == name
                )
            )
        )
        count = result.scalar() or 0
        return count > 0
    
    async def _get_task_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()
    
    def _generate_access_token(self) -> str:
        """生成访问令牌"""
        token_bytes = secrets.token_bytes(32)
        return "eclaw_" + token_bytes.hex()
    
    def _build_gateway_env(self, token: str, instance_type: str) -> Dict[str, str]:
        """构建Gateway环境变量"""
        if instance_type.lower() != "openclaw":
            return {}
        
        # 从环境变量获取Gateway配置
        base_url = os.environ.get("E_CLAW_LLM_GATEWAY_BASE_URL", "")
        
        env = {}
        
        if base_url:
            env["CLAWMANAGER_LLM_BASE_URL"] = base_url
            env["OPENAI_BASE_URL"] = base_url
            env["OPENAI_API_BASE"] = base_url
        
        env["CLAWMANAGER_LLM_API_KEY"] = token
        env["OPENAI_API_KEY"] = token
        
        env["CLAWMANAGER_LLM_MODEL"] = "auto"
        env["CLAWMANAGER_LLM_PROVIDER"] = "openai-compatible"
        env["CLAWMANAGER_INSTANCE_TOKEN"] = token
        
        return env


async def create_default_quota(db: AsyncSession, user_id: str) -> UserQuota:
    """为用户创建默认配额"""
    quota = UserQuota(
        user_id=user_id,
        max_instances=5,
        max_cpu_cores=16,
        max_memory_gb=64,
        max_storage_gb=500,
        max_gpu_count=0
    )
    db.add(quota)
    await db.commit()
    return quota