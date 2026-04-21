"""
E-Claw 系统镜像设置服务
支持可配置的镜像模板，类似ClawManager的SystemImageSettingService
"""
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import SystemImageSetting


# 支持的实例类型
ORDERED_SYSTEM_IMAGE_TYPES = [
    "openclaw",
    "ubuntu",
    "webtop",
    "debian",
    "centos",
    "custom"
]

SUPPORTED_SYSTEM_IMAGE_TYPES = {
    "openclaw": "OpenClaw Desktop",
    "ubuntu": "Ubuntu Desktop",
    "webtop": "Webtop Desktop",
    "debian": "Debian Desktop",
    "centos": "CentOS Desktop",
    "custom": "Custom Image"
}

# 默认镜像设置
DEFAULT_SYSTEM_IMAGE_SETTINGS = {
    "openclaw": "ghcr.io/yuan-lab-llm/clawmanager-openclaw-image/openclaw:latest",
    "ubuntu": "lscr.io/linuxserver/webtop:ubuntu-xfce",
    "webtop": "lscr.io/linuxserver/webtop:ubuntu-xfce",
    "debian": "docker.io/clawreef/debian-desktop:12",
    "centos": "docker.io/clawreef/centos-desktop:9",
    "custom": "registry.example.com/your-custom-image:latest"
}

# 默认启用的镜像类型
DEFAULT_ENABLED_SYSTEM_IMAGE_TYPES = {
    "openclaw": True,
    "ubuntu": True,
    "webtop": False,
    "debian": False,
    "centos": False,
    "custom": False
}


class SystemImageService:
    """系统镜像设置服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_images(self) -> List[Dict[str, Any]]:
        """获取所有镜像设置"""
        result = await self.db.execute(
            select(SystemImageSetting)
        )
        stored_settings = result.scalars().all()
        
        # 转换为字典
        by_type = {s.instance_type: s for s in stored_settings}
        
        # 构建有序的设置列表
        settings = []
        for instance_type in ORDERED_SYSTEM_IMAGE_TYPES:
            display_name = SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, f"{instance_type} Image")
            
            if instance_type in by_type:
                item = by_type[instance_type]
                if not item.display_name:
                    item.display_name = display_name
                settings.append({
                    "id": item.id,
                    "instance_type": item.instance_type,
                    "display_name": item.display_name,
                    "image": item.image,
                    "is_enabled": item.is_enabled,
                    "description": item.description
                })
            else:
                # 使用默认值
                settings.append({
                    "id": None,
                    "instance_type": instance_type,
                    "display_name": display_name,
                    "image": DEFAULT_SYSTEM_IMAGE_SETTINGS.get(instance_type, ""),
                    "is_enabled": DEFAULT_ENABLED_SYSTEM_IMAGE_TYPES.get(instance_type, False),
                    "description": None
                })
        
        return settings
    
    async def get_image(self, instance_type: str) -> Optional[Dict[str, Any]]:
        """获取指定类型的镜像设置"""
        instance_type = instance_type.lower().strip()
        
        result = await self.db.execute(
            select(SystemImageSetting).where(
                SystemImageSetting.instance_type == instance_type
            )
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            return {
                "id": setting.id,
                "instance_type": setting.instance_type,
                "display_name": setting.display_name,
                "image": setting.image,
                "is_enabled": setting.is_enabled,
                "description": setting.description
            }
        
        # 返回默认设置
        if instance_type in DEFAULT_SYSTEM_IMAGE_SETTINGS:
            return {
                "id": None,
                "instance_type": instance_type,
                "display_name": SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, ""),
                "image": DEFAULT_SYSTEM_IMAGE_SETTINGS.get(instance_type, ""),
                "is_enabled": DEFAULT_ENABLED_SYSTEM_IMAGE_TYPES.get(instance_type, False),
                "description": None
            }
        
        return None
    
    async def get_runtime_image(self, instance_type: str) -> tuple[str, bool]:
        """
        获取运行时镜像地址
        返回 (image_url, is_enabled)
        """
        instance_type = instance_type.lower().strip()
        
        result = await self.db.execute(
            select(SystemImageSetting).where(
                SystemImageSetting.instance_type == instance_type
            )
        )
        setting = result.scalar_one_or_none()
        
        if setting is None:
            # 使用默认值
            image = DEFAULT_SYSTEM_IMAGE_SETTINGS.get(instance_type, "")
            enabled = DEFAULT_ENABLED_SYSTEM_IMAGE_TYPES.get(instance_type, False)
            return image, enabled and bool(image)
        
        if not setting.is_enabled:
            return "", False
        
        image = setting.image.strip()
        return image, bool(image)
    
    async def save_image(self, instance_type: str, image: str, display_name: str = None, description: str = None) -> Dict[str, Any]:
        """保存镜像设置"""
        instance_type = instance_type.lower().strip()
        
        if instance_type not in SUPPORTED_SYSTEM_IMAGE_TYPES:
            raise ValueError(f"Unsupported instance type: {instance_type}")
        
        image = image.strip()
        if not image:
            raise ValueError("Image is required")
        
        if not display_name:
            display_name = SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, "")
        
        # 检查是否已存在
        result = await self.db.execute(
            select(SystemImageSetting).where(
                SystemImageSetting.instance_type == instance_type
            )
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.image = image
            setting.display_name = display_name
            setting.description = description
            setting.is_enabled = True
        else:
            setting = SystemImageSetting(
                instance_type=instance_type,
                display_name=display_name,
                image=image,
                description=description,
                is_enabled=True
            )
            self.db.add(setting)
        
        await self.db.commit()
        await self.db.refresh(setting)
        
        return {
            "id": setting.id,
            "instance_type": setting.instance_type,
            "display_name": setting.display_name,
            "image": setting.image,
            "is_enabled": setting.is_enabled,
            "description": setting.description
        }
    
    async def delete_image(self, instance_type: str) -> bool:
        """删除（禁用）镜像设置"""
        instance_type = instance_type.lower().strip()
        
        if instance_type not in SUPPORTED_SYSTEM_IMAGE_TYPES:
            raise ValueError(f"Unsupported instance type: {instance_type}")
        
        result = await self.db.execute(
            select(SystemImageSetting).where(
                SystemImageSetting.instance_type == instance_type
            )
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.is_enabled = False
            await self.db.commit()
            return True
        
        # 如果不存在，则创建一个禁用的记录
        setting = SystemImageSetting(
            instance_type=instance_type,
            display_name=SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, ""),
            image=DEFAULT_SYSTEM_IMAGE_SETTINGS.get(instance_type, ""),
            is_enabled=False,
            description=None
        )
        self.db.add(setting)
        await self.db.commit()
        
        return True


# 获取默认镜像配置（不依赖数据库）
def get_default_image_template(instance_type: str) -> Optional[Dict[str, Any]]:
    """获取默认镜像模板（用于API端点返回）"""
    instance_type = instance_type.lower().strip()
    
    if instance_type not in SUPPORTED_SYSTEM_IMAGE_TYPES:
        return None
    
    return {
        "id": instance_type,
        "name": SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, ""),
        "description": f"{SUPPORTED_SYSTEM_IMAGE_TYPES.get(instance_type, 'Desktop')} Environment",
        "image": DEFAULT_SYSTEM_IMAGE_SETTINGS.get(instance_type, ""),
        "default_port": 3001,
        "is_enabled": DEFAULT_ENABLED_SYSTEM_IMAGE_TYPES.get(instance_type, False),
        "env_vars": get_default_env_vars(instance_type)
    }


def get_default_env_vars(instance_type: str) -> Dict[str, str]:
    """获取默认环境变量"""
    if instance_type == "webtop":
        return {
            "CUSTOM_USER": "abc",
            "PASSWORD": "",
            "TITLE": "E-Claw Webtop",
            "SUBFOLDER": "/"
        }
    return {}


def get_all_default_templates() -> List[Dict[str, Any]]:
    """获取所有默认镜像模板"""
    templates = []
    for instance_type in ORDERED_SYSTEM_IMAGE_TYPES:
        template = get_default_image_template(instance_type)
        if template:
            templates.append(template)
    return templates