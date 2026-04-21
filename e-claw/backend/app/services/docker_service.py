"""
E-Claw Docker环境管理服务
为每个任务创建独立的Docker容器，支持多种镜像模板
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import subprocess
import json


# Docker镜像模板配置
DOCKER_IMAGE_TEMPLATES = [
    {
        "id": "openclaw",
        "name": "OpenClaw镜像",
        "description": "OpenClaw工作环境，包含完整的AI任务处理能力",
        "image": "openclaw:local",
        "default_port": 18789,
        "env_vars": {
            "OPENCLAW_GATEWAY_TOKEN": "{token}"
        }
    },
    {
        "id": "linux",
        "name": "Linux基础镜像",
        "description": "通用的Linux工作环境，适合通用任务",
        "image": "ubuntu:22.04",
        "default_port": 22,
        "env_vars": {}
    }
]


class DockerService:
    """Docker容器管理服务"""
    
    # 基础端口号
    BASE_PORT = 18789
    MAX_CONTAINERS = 100
    
    def __init__(self):
        self.used_ports = set()
    
    def get_image_templates(self) -> List[Dict[str, Any]]:
        """获取所有可用的镜像模板"""
        return DOCKER_IMAGE_TEMPLATES
    
    def get_image_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取指定ID的镜像模板"""
        for template in DOCKER_IMAGE_TEMPLATES:
            if template["id"] == template_id:
                return template
        return None
    
    async def create_environment(
        self, 
        task_id: str, 
        task_name: str,
        user_id: str,
        image_template_id: str = "openclaw"
    ) -> Dict[str, Any]:
        """
        为任务创建Docker环境
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            user_id: 用户ID
            image_template_id: 镜像模板ID
            
        Returns:
            {
                "container_id": "xxx",
                "container_name": "xxx",
                "docker_url": "http://localhost:18789",
                "port": 18789,
                "status": "running"
            }
        """
        # 获取镜像模板配置
        template = self.get_image_template(image_template_id)
        if not template:
            return {"error": f"未知的镜像模板: {image_template_id}"}
        
        # 生成唯一的容器名称
        container_name = f"eclaw-{image_template_id}-{task_id[:8]}"
        
        # 分配端口
        port = await self._allocate_port(template.get("default_port", 18800))
        
        # 停止已有容器（如果存在）
        await self._stop_container(container_name)
        await self._remove_container(container_name)
        
        # 根据镜像类型构建不同的docker run命令
        if image_template_id == "openclaw":
            return await self._create_openclaw_container(
                container_name, port, task_id, template
            )
        elif image_template_id == "linux":
            return await self._create_linux_container(
                container_name, port, task_id, template
            )
        else:
            return await self._create_generic_container(
                container_name, port, task_id, template
            )
    
    async def _create_openclaw_container(
        self,
        container_name: str,
        port: int,
        task_id: str,
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建OpenClaw容器"""
        # 构建docker run命令
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:18789",
            "-e", f"OPENCLAW_GATEWAY_TOKEN={uuid.uuid4().hex}",
            "--restart", "unless-stopped",
            template["image"]
        ]
        
        return await self._run_docker_command(cmd, container_name, port, task_id)
    
    async def _create_linux_container(
        self,
        container_name: str,
        port: int,
        task_id: str,
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建Linux容器"""
        # 构建docker run命令 - 使用SSH
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:22",
            "-e", "ACCEPT_EULA=Y",
            "-e", "DEBIAN_FRONTEND=noninteractive",
            "--restart", "unless-stopped",
            "--shm-size", "2g",
            template["image"],
            "bash", "-c",
            "apt-get update && apt-get install -y openssh-server && /usr/sbin/sshd"
        ]
        
        return await self._run_docker_command(cmd, container_name, port, task_id)
    
    async def _create_generic_container(
        self,
        container_name: str,
        port: int,
        task_id: str,
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建通用容器"""
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--restart", "unless-stopped",
            template["image"]
        ]
        
        return await self._run_docker_command(cmd, container_name, port, task_id)
    
    async def _run_docker_command(
        self,
        cmd: List[str],
        container_name: str,
        port: int,
        task_id: str
    ) -> Dict[str, Any]:
        """执行docker命令并返回结果"""
        try:
            # 执行docker run
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                # 如果镜像不存在，尝试拉取并重试
                image = cmd[-1] if "run" in cmd else "openclaw:local"
                pull_result = subprocess.run(
                    ["docker", "pull", image],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if pull_result.returncode == 0:
                    # 重试创建
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            container_id = result.stdout.strip()
            
            # 等待容器启动
            await asyncio.sleep(3)
            
            # 检查容器状态
            status = await self._get_container_status(container_id)
            
            return {
                "container_id": container_id,
                "container_name": container_name,
                "docker_url": f"http://localhost:{port}",
                "port": port,
                "status": status
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "容器创建超时"}
        except FileNotFoundError:
            return {"error": "Docker未安装或不可用"}
        except Exception as e:
            return {"error": f"创建容器失败: {str(e)}"}
    
    # 保留原有方法以兼容旧代码
    async def create_openclaw_environment(
        self, 
        task_id: str, 
        task_name: str,
        user_id: str
    ) -> Dict[str, Any]:
        """为任务创建OpenClaw Docker环境（兼容旧接口）"""
        return await self.create_environment(task_id, task_name, user_id, "openclaw")
    
    async def _create_with_compose(
        self, 
        task_id: str, 
        task_name: str, 
        port: int
    ) -> Dict[str, Any]:
        """使用docker-compose创建环境"""
        container_name = f"openclaw-task-{task_id[:8]}"
        
        # 创建临时docker-compose配置
        compose_config = f"""services:
  openclaw:
    image: openclaw:local
    container_name: {container_name}
    ports:
      - "{port}:18789"
      - "{port+1}:18790"
    environment:
      - OPENCLAW_GATEWAY_TOKEN={uuid.uuid4().hex}
    restart: unless-stopped
"""
        # 写入临时compose文件
        compose_file = f"/tmp/openclaw-{task_id[:8]}.yml"
        with open(compose_file, "w") as f:
            f.write(compose_config)
        
        try:
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd="/tmp"
            )
            
            if result.returncode == 0:
                ps_result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.ID}}"],
                    capture_output=True,
                    text=True
                )
                container_id = ps_result.stdout.strip()
                await asyncio.sleep(3)
                
                return {
                    "container_id": container_id,
                    "container_name": container_name,
                    "docker_url": f"http://localhost:{port}",
                    "port": port,
                    "status": "running"
                }
            else:
                return {"error": f"docker-compose创建失败: {result.stderr}"}
        except Exception as e:
            return {"error": f"创建失败: {str(e)}"}
        finally:
            try:
                import os
                os.remove(compose_file)
            except:
                pass
    
    async def start_container(self, container_name: str) -> Dict[str, Any]:
        """启动容器"""
        try:
            result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                await asyncio.sleep(2)
                status = await self._get_container_status_by_name(container_name)
                return {"status": status, "message": "容器已启动"}
            else:
                return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    async def stop_container(self, container_name: str) -> Dict[str, Any]:
        """停止容器"""
        try:
            result = subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {"status": "stopped", "message": "容器已停止"}
            else:
                return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    async def remove_container(self, container_name: str) -> Dict[str, Any]:
        """删除容器"""
        try:
            # 先停止容器
            await self.stop_container(container_name)
            
            # 删除容器
            result = subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {"status": "removed", "message": "容器已删除"}
            else:
                return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    async def _stop_container(self, container_name: str):
        """停止容器（内部方法）"""
        try:
            subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                timeout=30
            )
        except:
            pass
    
    async def _remove_container(self, container_name: str):
        """删除容器（内部方法）"""
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=30
            )
        except:
            pass
    
    async def get_container_status(self, container_name: str) -> str:
        """获取容器状态"""
        return await self._get_container_status_by_name(container_name)
    
    async def _get_container_status_by_name(self, container_name: str) -> str:
        """通过名称获取容器状态"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout.strip()
            if "Up" in output:
                return "running"
            elif "Exited" in output:
                return "stopped"
            else:
                return "not_found"
        except:
            return "error"
    
    async def _get_container_status(self, container_id: str) -> str:
        """通过ID获取容器状态"""
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                capture_output=True,
                text=True
            )
            
            return result.stdout.strip()
        except:
            return "not_found"
    
    async def _allocate_port(self) -> int:
        """分配可用端口"""
        # 简单实现：查找未被使用的端口
        for port in range(self.BASE_PORT, self.BASE_PORT + self.MAX_CONTAINERS):
            if port not in self.used_ports:
                # 检查端口是否被docker占用
                result = subprocess.run(
                    ["docker", "ps", "--format", "{{.Ports}}"],
                    capture_output=True,
                    text=True
                )
                
                port_str = f":{port}-"
                if port_str not in result.stdout:
                    self.used_ports.add(port)
                    return port
        
        raise Exception("无可用端口")
    
    async def get_container_info(self, container_name: str) -> Dict[str, Any]:
        """获取容器详细信息"""
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                if info:
                    return {
                        "id": info[0].get("Id", ""),
                        "name": info[0].get("Name", "").strip("/"),
                        "status": info[0].get("State", {}).get("Status", ""),
                        "created": info[0].get("Created", ""),
                        "ports": info[0].get("NetworkSettings", {}).get("Ports", {})
                    }
            return {"error": "容器不存在"}
        except Exception as e:
            return {"error": str(e)}


# 全局Docker服务实例
docker_service = DockerService()