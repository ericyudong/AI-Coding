"""
E-Claw 实例运行时配置模块
定义不同实例类型的运行时配置（镜像、端口、挂载路径、环境变量）
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class InstanceRuntimeConfig:
    """实例运行时配置"""
    image: str
    port: int
    mount_path: str
    env: Dict[str, str]


def build_runtime_config(
    instance_type: str,
    os_type: str = "linux",
    os_version: str = "latest",
    custom_registry: str = None,
    custom_tag: str = None
) -> InstanceRuntimeConfig:
    """
    根据实例类型构建运行时配置
    
    Args:
        instance_type: 实例类型 (openclaw, ubuntu, webtop, debian, centos, custom)
        os_type: 操作系统类型
        os_version: 操作系统版本
        custom_registry: 自定义镜像仓库
        custom_tag: 自定义镜像标签
        
    Returns:
        InstanceRuntimeConfig: 运行时配置
    """
    # 如果提供了完整镜像地址（只有registry，没有tag）
    if custom_registry and not custom_tag:
        return InstanceRuntimeConfig(
            image=custom_registry.strip(),
            port=default_port_for_instance_type(instance_type),
            mount_path=default_mount_path_for_instance_type(instance_type),
            env=default_env_for_instance_type(instance_type)
        )
    
    # 构建镜像地址
    default_registry = os.environ.get("E_CLAW_IMAGE_REGISTRY", "docker.io/clawreef")
    registry = custom_registry if custom_registry else default_registry
    tag = custom_tag if custom_tag else os_version
    
    config = InstanceRuntimeConfig(
        image="",
        port=3001,
        mount_path="/home/user/data",
        env={}
    )
    
    instance_type = instance_type.lower().strip() if instance_type else ""
    
    # 根据实例类型设置配置
    if instance_type == "ubuntu":
        config.image = "lscr.io/linuxserver/webtop:ubuntu-xfce"
        config.port = 3001
        config.mount_path = "/config"
    elif instance_type == "webtop":
        config.image = "lscr.io/linuxserver/webtop:ubuntu-xfce"
        config.port = 3001
        config.mount_path = "/config"
        config.env = {
            "CUSTOM_USER": "abc",
            "PASSWORD": "",
            "TITLE": "E-Claw Webtop",
            "SUBFOLDER": "/"
        }
    elif instance_type == "openclaw":
        # 优先使用环境变量中的配置
        default_openclaw_image = os.environ.get(
            "E_CLAW_OPENCLAW_IMAGE",
            "ghcr.io/yuan-lab-llm/clawmanager-openclaw-image/openclaw:latest"
        )
        if not custom_registry and not custom_tag:
            config.image = default_openclaw_image
        else:
            config.image = f"{registry}/openclaw-desktop:{tag}"
        config.port = 3001
        config.mount_path = "/home/user/data"
    elif instance_type == "debian":
        config.image = f"{registry}/debian-desktop:{tag}"
        config.port = 3001
        config.mount_path = "/home/user/data"
    elif instance_type == "centos":
        config.image = f"{registry}/centos-desktop:{tag}"
        config.port = 3001
        config.mount_path = "/home/user/data"
    else:
        # custom 或其他类型
        config.image = f"{registry}/{os_type}-desktop:{tag}"
        config.port = 3001
        config.mount_path = "/home/user/data"
    
    return config


def default_port_for_instance_type(instance_type: str) -> int:
    """获取实例类型的默认端口"""
    instance_type = instance_type.lower().strip() if instance_type else ""
    if instance_type in ["ubuntu", "webtop", "openclaw"]:
        return 3001
    return 3001


def default_mount_path_for_instance_type(instance_type: str) -> str:
    """获取实例类型的默认挂载路径"""
    instance_type = instance_type.lower().strip() if instance_type else ""
    if instance_type in ["ubuntu", "webtop"]:
        return "/config"
    return "/home/user/data"


def default_env_for_instance_type(instance_type: str) -> Dict[str, str]:
    """获取实例类型的默认环境变量"""
    instance_type = instance_type.lower().strip() if instance_type else ""
    
    if instance_type == "webtop":
        return {
            "CUSTOM_USER": "abc",
            "PASSWORD": "",
            "TITLE": "E-Claw Webtop",
            "SUBFOLDER": "/"
        }
    elif instance_type == "openclaw":
        # OpenCLAW 需要配置LLM Gateway
        return get_openclaw_env()
    
    return {}


def get_openclaw_env() -> Dict[str, str]:
    """获取OpenCLAW的环境变量配置"""
    gateway_base_url = os.environ.get("E_CLAW_LLM_GATEWAY_BASE_URL", "")
    gateway_token = os.environ.get("E_CLAW_LLM_GATEWAY_TOKEN", "")
    
    env = {}
    
    if gateway_base_url:
        env["CLAWMANAGER_LLM_BASE_URL"] = gateway_base_url
        env["OPENAI_BASE_URL"] = gateway_base_url
        env["OPENAI_API_BASE"] = gateway_base_url
    
    if gateway_token:
        env["CLAWMANAGER_LLM_API_KEY"] = gateway_token
        env["OPENAI_API_KEY"] = gateway_token
    
    env["CLAWMANAGER_LLM_MODEL"] = "auto"
    env["CLAWMANAGER_LLM_PROVIDER"] = "openai-compatible"
    
    return env


def with_instance_proxy_env(
    instance_type: str,
    instance_id: int,
    base_env: Dict[str, str]
) -> Dict[str, str]:
    """
    合并代理环境变量
    
    Args:
        instance_type: 实例类型
        instance_id: 实例ID
        base_env: 基础环境变量
        
    Returns:
        合并后的环境变量
    """
    merged = dict(base_env)
    
    # 添加 egress proxy 配置
    proxy_url = os.environ.get("E_CLAW_EGRESS_PROXY_URL", "")
    if proxy_url:
        no_proxy = os.environ.get("E_CLAW_NO_PROXY", get_default_no_proxy_list())
        merged["HTTP_PROXY"] = proxy_url
        merged["HTTPS_PROXY"] = proxy_url
        merged["http_proxy"] = proxy_url
        merged["https_proxy"] = proxy_url
        merged["NO_PROXY"] = no_proxy
        merged["no_proxy"] = no_proxy
    
    # 为webtop类型添加subfolder配置
    instance_type = instance_type.lower().strip() if instance_type else ""
    if instance_type in ["ubuntu", "webtop", "openclaw"]:
        merged["SUBFOLDER"] = f"/api/v1/instances/{instance_id}/proxy/"
    
    return merged


def get_default_no_proxy_list() -> str:
    """获取默认的NO_PROXY列表"""
    system_namespace = os.environ.get("E_CLAW_SYSTEM_NAMESPACE", "e-claw-system")
    
    service_names = [
        "localhost",
        "127.0.0.1",
        "e-claw-frontend",
        "e-claw-gateway",
        "e-claw-egress-proxy",
    ]
    
    if system_namespace:
        service_names.extend([
            f"e-claw-frontend.{system_namespace}",
            f"e-claw-frontend.{system_namespace}.svc",
            f"e-claw-frontend.{system_namespace}.svc.cluster.local",
            f"e-claw-gateway.{system_namespace}",
            f"e-claw-gateway.{system_namespace}.svc",
            f"e-claw-gateway.{system_namespace}.svc.cluster.local",
            f"e-claw-egress-proxy.{system_namespace}",
            f"e-claw-egress-proxy.{system_namespace}.svc",
            f"e-claw-egress-proxy.{system_namespace}.svc.cluster.local",
        ])
    
    return ",".join(service_names)


def uses_webtop_image(instance_type: str) -> bool:
    """检查是否使用webtop类型的镜像"""
    instance_type = instance_type.lower().strip() if instance_type else ""
    return instance_type in ["ubuntu", "webtop", "openclaw"]


def get_gpu_resource_config(gpu_enabled: bool, gpu_count: int = 0) -> Dict[str, Any]:
    """获取GPU资源配置"""
    if not gpu_enabled or gpu_count <= 0:
        return {
            "limits": {},
            "requests": {}
        }
    
    # nvidia.com/gpu 资源
    return {
        "limits": {
            "nvidia.com/gpu": gpu_count
        },
        "requests": {
            "nvidia.com/gpu": gpu_count
        }
    }


def get_cpu_memory_config(
    cpu_cores: int,
    memory_gb: int,
    gpu_enabled: bool = False,
    gpu_count: int = 0
) -> Dict[str, Any]:
    """
    获取CPU和内存资源配置
    
    Args:
        cpu_cores: CPU核心数
        memory_gb: 内存大小(GB)
        gpu_enabled: 是否启用GPU
        gpu_count: GPU数量
        
    Returns:
        资源限制配置
    """
    resources = {
        "requests": {
            "cpu": f"{cpu_cores}m",
            "memory": f"{memory_gb}Gi"
        },
        "limits": {
            "cpu": f"{cpu_cores * 1000}m",
            "memory": f"{memory_gb}Gi"
        }
    }
    
    # 添加GPU配置
    if gpu_enabled and gpu_count > 0:
        resources["limits"]["nvidia.com/gpu"] = gpu_count
        resources["requests"]["nvidia.com/gpu"] = gpu_count
    
    return resources