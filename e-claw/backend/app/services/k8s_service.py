"""
E-Claw Kubernetes环境管理服务
基于Kubernetes的容器管理，支持Pod、PVC、Service等资源
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from kubernetes import client, config
from kubernetes.client.rest import ApiException


# Kubernetes镜像模板配置
K8S_IMAGE_TEMPLATES = [
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
    },
    {
        "id": "webtop",
        "name": "WebTop桌面",
        "description": "基于Web的Linux桌面环境",
        "image": "lscr.io/linuxserver/webtop:latest",
        "default_port": 3000,
        "env_vars": {
            "PUID": "1000",
            "PGID": "1000",
            "TZ": "Asia/Shanghai"
        }
    }
]


class K8sService:
    """Kubernetes容器管理服务"""
    
    # 基础端口号
    BASE_PORT = 18789
    MAX_INSTANCES = 100
    NAMESPACE = "e-claw-system"
    
    def __init__(self):
        self.used_ports = set()
        self._init_k8s_client()
    
    def _init_k8s_client(self):
        """初始化K8s客户端"""
        import os
        try:
            # 尝试加载in-cluster配置
            config.load_incluster_config()
        except config.ConfigException:
            # 如果不在集群内，尝试加载本地配置
            try:
                # 首先尝试从环境变量读取kubeconfig路径
                kubeconfig_path = os.environ.get('KUBECONFIG')
                if kubeconfig_path and os.path.exists(kubeconfig_path):
                    config.load_kube_config(config_file=kubeconfig_path)
                else:
                    # 使用默认路径
                    config.load_kube_config()
            except Exception:
                # 如果没有配置，使用动态配置
                pass
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.networking_v1 = client.NetworkingV1Api()
    
    def get_image_templates(self) -> List[Dict[str, Any]]:
        """获取所有可用的镜像模板"""
        return K8S_IMAGE_TEMPLATES
    
    def get_image_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取指定ID的镜像模板"""
        for template in K8S_IMAGE_TEMPLATES:
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
        为任务创建Kubernetes环境
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            user_id: 用户ID
            image_template_id: 镜像模板ID
            
        Returns:
            {
                "pod_name": "xxx",
                "pod_namespace": "e-claw-system",
                "service_name": "xxx",
                "service_url": "http://localhost:18789",
                "port": 18789,
                "status": "running"
            }
        """
        # 获取镜像模板配置
        template = self.get_image_template(image_template_id)
        if not template:
            return {"error": f"未知的镜像模板: {image_template_id}"}
        
        # 生成唯一的资源名称
        resource_name = f"eclaw-{image_template_id}-{task_id[:8]}"
        
        # 分配端口
        port = await self._allocate_port(template.get("default_port", 18800))
        
        try:
            # 创建PVC存储
            await self._create_pvc(resource_name)
            
            # 创建Pod
            pod = await self._create_pod(resource_name, port, task_id, template, user_id)
            
            # 创建Service
            service = await self._create_service(resource_name, port, template)
            
            return {
                "pod_name": resource_name,
                "pod_namespace": self.NAMESPACE,
                "service_name": resource_name,
                "service_url": f"http://localhost:{port}",
                "port": port,
                "status": "running"
            }
            
        except Exception as e:
            # 清理已创建的资源
            await self._cleanup_resources(resource_name)
            return {"error": f"创建环境失败: {str(e)}"}
    
    async def _create_pvc(self, resource_name: str) -> None:
        """创建PersistentVolumeClaim"""
        # 使用V1PersistentVolumeClaim对象直接构建
        pvc = client.V1PersistentVolumeClaim(
            api_version="v1",
            kind="PersistentVolumeClaim",
            metadata=client.V1ObjectMeta(
                name=f"{resource_name}-data",
                namespace=self.NAMESPACE
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": "10Gi"}
                ),
                storage_class_name="standard",
                volume_mode="Filesystem"
            )
        )
        
        try:
            self.core_v1.create_namespaced_persistent_volume_claim(
                namespace=self.NAMESPACE,
                body=pvc
            )
        except ApiException as e:
            if e.status == 409:  # Already exists
                pass
            else:
                raise
    
    async def _create_pod(
        self, 
        resource_name: str, 
        port: int, 
        task_id: str, 
        template: Dict[str, Any],
        user_id: str
    ) -> None:
        """创建Pod"""
        token = uuid.uuid4().hex
        
        # 构建环境变量
        env_vars = []
        for key, value in template.get("env_vars", {}).items():
            env_vars.append(client.V1EnvVar(
                name=key,
                value=value.format(token=token)
            ))
        
        # 添加用户ID和任务ID
        env_vars.append(client.V1EnvVar(name="USER_ID", value=user_id))
        env_vars.append(client.V1EnvVar(name="TASK_ID", value=task_id))
        
        pod_manifest = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=resource_name,
                namespace=self.NAMESPACE,
                labels={
                    "app": "e-claw",
                    "task_id": task_id,
                    "user_id": user_id,
                    "template": template["id"]
                }
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="main",
                        image=template["image"],
                        ports=[client.V1ContainerPort(container_port=port)],
                        env=env_vars,
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="data",
                                mount_path="/data"
                            )
                        ],
                        resources=client.V1ResourceRequirements(
                            requests={
                                "cpu": "500m",
                                "memory": "1Gi"
                            },
                            limits={
                                "cpu": "2000m",
                                "memory": "4Gi"
                            }
                        )
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="data",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=f"{resource_name}-data"
                        )
                    )
                ],
                restart_policy="Always"
            )
        )
        
        try:
            self.core_v1.create_namespaced_pod(
                namespace=self.NAMESPACE,
                body=pod_manifest
            )
        except ApiException as e:
            if e.status == 409:  # Already exists
                # 删除旧的Pod后重新创建
                self.core_v1.delete_namespaced_pod(
                    name=resource_name,
                    namespace=self.NAMESPACE,
                    body=client.V1DeleteOptions()
                )
                await asyncio.sleep(2)
                self.core_v1.create_namespaced_pod(
                    namespace=self.NAMESPACE,
                    body=pod_manifest
                )
            else:
                raise
    
    async def _create_service(
        self, 
        resource_name: str, 
        port: int, 
        template: Dict[str, Any]
    ) -> None:
        """创建Service"""
        service_manifest = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=resource_name,
                namespace=self.NAMESPACE
            ),
            spec=client.V1ServiceSpec(
                selector={"app": "e-claw", "name": resource_name},
                ports=[
                    client.V1ServicePort(
                        name="http",
                        port=port,
                        target_port=port,
                        protocol="TCP"
                    )
                ],
                type="NodePort"
            )
        )
        
        try:
            self.core_v1.create_namespaced_service(
                namespace=self.NAMESPACE,
                body=service_manifest
            )
        except ApiException as e:
            if e.status == 409:  # Already exists
                pass
            else:
                raise
    
    async def _cleanup_resources(self, resource_name: str) -> None:
        """清理资源"""
        try:
            # 删除Service
            self.core_v1.delete_namespaced_service(
                name=resource_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except:
            pass
        
        try:
            # 删除Pod
            self.apps_v1.delete_namespaced_pod(
                name=resource_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except:
            pass
        
        try:
            # 删除PVC
            self.core_v1.delete_namespaced_persistent_volume_claim(
                name=f"{resource_name}-data",
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except:
            pass
    
    async def start_environment(self, resource_name: str) -> Dict[str, Any]:
        """启动环境"""
        try:
            self.apps_v1.read_namespaced_pod(name=resource_name, namespace=self.NAMESPACE)
            # 如果存在则启动
            self.apps_v1.patch_namespaced_pod(
                name=resource_name,
                namespace=self.NAMESPACE,
                body={"spec": {"activeDeadline": None}}
            )
            return {"status": "running", "message": "环境已启动"}
        except ApiException as e:
            return {"error": f"启动失败: {e.reason}"}
    
    async def stop_environment(self, resource_name: str) -> Dict[str, Any]:
        """停止环境"""
        try:
            self.apps_v1.delete_namespaced_pod(
                name=resource_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
            return {"status": "stopped", "message": "环境已停止"}
        except ApiException as e:
            return {"error": f"停止失败: {e.reason}"}
    
    async def remove_environment(self, resource_name: str) -> Dict[str, Any]:
        """删除环境"""
        try:
            await self._cleanup_resources(resource_name)
            return {"status": "removed", "message": "环境已删除"}
        except Exception as e:
            return {"error": f"删除失败: {str(e)}"}
    
    async def get_environment_status(self, resource_name: str) -> str:
        """获取环境状态"""
        try:
            pod = self.apps_v1.read_namespaced_pod(
                name=resource_name, 
                namespace=self.NAMESPACE
            )
            return pod.status.phase.lower()
        except ApiException:
            return "not_found"
    
    async def get_environment_info(self, resource_name: str) -> Dict[str, Any]:
        """获取环境详细信息"""
        try:
            pod = self.apps_v1.read_namespaced_pod(
                name=resource_name, 
                namespace=self.NAMESPACE
            )
            return {
                "name": pod.metadata.name,
                "status": pod.status.phase,
                "ip": pod.status.pod_ip,
                "node": pod.spec.node_name,
                "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
            }
        except ApiException as e:
            return {"error": str(e)}
    
    async def _allocate_port(self, base_port: int = None) -> int:
        """分配可用端口"""
        if base_port is None:
            base_port = self.BASE_PORT
            
        for port in range(base_port, base_port + self.MAX_INSTANCES):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        
        raise Exception("无可用端口")
    
    async def list_environments(self, user_id: str = None) -> List[Dict[str, Any]]:
        """列出所有环境"""
        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.NAMESPACE,
                label_selector="app=e-claw"
            )
            
            environments = []
            for pod in pods.items:
                if user_id and pod.metadata.labels.get("user_id") != user_id:
                    continue
                    
                environments.append({
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ip": pod.status.pod_ip,
                    "template": pod.metadata.labels.get("template", "unknown"),
                    "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
                })
            
            return environments
        except ApiException as e:
            return []
    
    async def get_cluster_resources(self) -> Dict[str, Any]:
        """获取集群资源信息"""
        try:
            # 获取节点信息
            nodes = self.core_v1.list_node()
            
            total_cpu = 0
            total_memory = 0
            available_cpu = 0
            available_memory = 0
            
            for node in nodes.items:
                cpu = node.status.capacity.get("cpu", "0")
                memory = node.status.capacity.get("memory", "0")
                
                total_cpu += int(cpu)
                # Convert memory from Ki to Gi
                total_memory += int(int(memory) / 1024 / 1024)
            
            # 获取使用中的Pod
            pods = self.core_v1.list_namespaced_pod(namespace=self.NAMESPACE)
            running_pods = len([p for p in pods.items if p.status.phase == "Running"])
            
            return {
                "total_nodes": len(nodes.items),
                "total_cpu": total_cpu,
                "total_memory_gb": total_memory,
                "running_pods": running_pods,
                "available_pods": self.MAX_INSTANCES - running_pods
            }
        except ApiException as e:
            return {"error": str(e)}
    
    async def list_nodes(self) -> List[Dict[str, Any]]:
        """获取集群节点列表"""
        try:
            nodes = self.core_v1.list_node()
            result = []
            
            for node in nodes.items:
                # 获取节点资源信息
                cpu_capacity = node.status.capacity.get("cpu", "0")
                memory_capacity = node.status.capacity.get("memory", "0")
                memory_capacity_gb = int(int(memory_capacity) / 1024 / 1024)
                
                # 获取allocatable资源
                cpu_allocatable = node.status.allocatable.get("cpu", "0") if node.status.allocatable else cpu_capacity
                memory_allocatable = node.status.allocatable.get("memory", "0") if node.status.allocatable else memory_capacity
                memory_allocatable_gb = int(int(memory_allocatable) / 1024 / 1024)
                
                # 确定节点角色
                roles = []
                if node.metadata.labels:
                    if node.metadata.labels.get("node-role.kubernetes.io/master"):
                        roles.append("master")
                    if node.metadata.labels.get("node-role.kubernetes.io/worker"):
                        roles.append("worker")
                    if node.metadata.labels.get("node-role.kubernetes.io/control-plane"):
                        roles.append("control-plane")
                if not roles:
                    roles.append("worker")
                
                # 获取节点状态
                node_status = "Ready"
                for condition in node.status.conditions:
                    if condition.type == "Ready":
                        node_status = "Ready" if condition.status == "True" else "NotReady"
                        break
                
                # 计算运行时间
                age = "Unknown"
                if node.metadata.creation_timestamp:
                    uptime = datetime.now() - node.metadata.creation_timestamp
                    days = uptime.days
                    age = f"{days}天"
                
                # 获取节点上的Pod数量
                pod_count = 0
                try:
                    pods = self.core_v1.list_pod_for_all_namespaces(
                        field_selector=f"spec.nodeName={node.metadata.name}"
                    )
                    pod_count = len(pods.items)
                except:
                    pass
                
                result.append({
                    "name": node.metadata.name,
                    "status": node_status,
                    "roles": ",".join(roles),
                    "age": age,
                    "version": node.status.node_info.kubelet_version if node.status.node_info else "Unknown",
                    "cpu_capacity": f"{cpu_capacity} cores",
                    "memory_capacity": f"{memory_capacity_gb} Gi",
                    "cpu_allocatable": f"{cpu_allocatable} cores",
                    "memory_allocatable": f"{memory_allocatable_gb} Gi",
                    "cpu_used": f"{int(cpu_capacity) - int(cpu_allocatable)} cores",
                    "memory_used": f"{memory_capacity_gb - memory_allocatable_gb} Gi",
                    "pod_count": pod_count,
                    "labels": node.metadata.labels or {}
                })
            
            return result
        except ApiException as e:
            return []
    
    async def list_namespaces(self) -> List[Dict[str, Any]]:
        """获取命名空间列表"""
        try:
            namespaces = self.core_v1.list_namespace()
            result = []
            
            for ns in namespaces.items:
                # 获取命名空间中的Pod数量
                pods = self.core_v1.list_namespaced_pod(namespace=ns.metadata.name)
                pod_count = len(pods.items)
                
                # 计算运行时间
                age = "Unknown"
                if ns.metadata.creation_timestamp:
                    uptime = datetime.now() - ns.metadata.creation_timestamp
                    days = uptime.days
                    age = f"{days}天"
                
                result.append({
                    "name": ns.metadata.name,
                    "status": ns.status.phase,
                    "age": age,
                    "pod_count": pod_count
                })
            
            return result
        except ApiException as e:
            return []
    
    # ==================== 新增：实例服务支持方法 ====================
    
    async def create_pvc(
        self,
        resource_name: str,
        storage_size_gb: int = 10,
        storage_class: str = ""
    ) -> Dict[str, Any]:
        """创建PersistentVolumeClaim"""
        pvc_name = f"{resource_name}-data"
        
        # 使用V1PersistentVolumeClaim对象直接构建
        pvc = client.V1PersistentVolumeClaim(
            api_version="v1",
            kind="PersistentVolumeClaim",
            metadata=client.V1ObjectMeta(
                name=pvc_name,
                namespace=self.NAMESPACE,
                labels={
                    "app": "e-claw",
                    "resource-name": resource_name
                }
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=client.V1ResourceRequirements(
                    requests={"storage": f"{storage_size_gb}Gi"}
                ),
                storage_class_name=storage_class if storage_class else "standard",
                volume_mode="Filesystem"
            )
        )
        
        try:
            self.core_v1.create_namespaced_persistent_volume_claim(
                namespace=self.NAMESPACE,
                body=pvc
            )
            return {"status": "created", "pvc_name": pvc_name}
        except ApiException as e:
            if e.status == 409:  # Already exists
                return {"status": "exists", "pvc_name": pvc_name}
            return {"error": str(e)}
    
    async def create_pod(
        self,
        resource_name: str,
        image: str,
        port: int = 3001,
        mount_path: str = "/data",
        env_vars: Dict[str, str] = None,
        resources: Dict[str, Any] = None,
        user_id: str = "",
        instance_id: str = ""
    ) -> Dict[str, Any]:
        """创建Pod"""
        # 构建环境变量
        env_list = []
        if env_vars:
            for key, value in env_vars.items():
                env_list.append(client.V1EnvVar(
                    name=key,
                    value=str(value)
                ))
        
        # 添加基础环境变量
        env_list.extend([
            client.V1EnvVar(name="USER_ID", value=str(user_id)),
            client.V1EnvVar(name="INSTANCE_ID", value=str(instance_id)),
        ])
        
        # 默认资源配置
        if not resources:
            resources = {
                "requests": {"cpu": "500m", "memory": "1Gi"},
                "limits": {"cpu": "2000m", "memory": "4Gi"}
            }
        
        pod_manifest = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=resource_name,
                namespace=self.NAMESPACE,
                labels={
                    "app": "e-claw",
                    "managed-by": "e-claw",
                    "resource-name": resource_name,
                    "user-id": str(user_id),
                    "instance-id": str(instance_id)
                }
            ),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="main",
                        image=image,
                        ports=[client.V1ContainerPort(container_port=port, name="http")],
                        env=env_list,
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="data",
                                mount_path=mount_path
                            )
                        ],
                        resources=client.V1ResourceRequirements(**resources)
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="data",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name=f"{resource_name}-data"
                        )
                    )
                ],
                restart_policy="Always"
            )
        )
        
        try:
            self.core_v1.create_namespaced_pod(
                namespace=self.NAMESPACE,
                body=pod_manifest
            )
            return {"status": "created", "pod_name": resource_name}
        except ApiException as e:
            if e.status == 409:  # Already exists - delete and recreate
                try:
                    self.core_v1.delete_namespaced_pod(
                        name=resource_name,
                        namespace=self.NAMESPACE,
                        body=client.V1DeleteOptions()
                    )
                    import asyncio
                    await asyncio.sleep(2)
                    self.core_v1.create_namespaced_pod(
                        namespace=self.NAMESPACE,
                        body=pod_manifest
                    )
                    return {"status": "recreated", "pod_name": resource_name}
                except Exception as re_err:
                    return {"error": f"Failed to recreate pod: {str(re_err)}"}
            return {"error": str(e)}
    
    async def create_service(
        self,
        resource_name: str,
        port: int = 3001
    ) -> Dict[str, Any]:
        """创建Service"""
        # 额外端口
        additional_ports = []
        if port == 3000 or port == 8082:
            additional_ports = [3000, 8082]
        
        ports = [
            client.V1ServicePort(
                name="http",
                port=port,
                target_port=port,
                protocol="TCP"
            )
        ]
        
        for extra_port in additional_ports:
            ports.append(client.V1ServicePort(
                name=f"http-{extra_port}",
                port=extra_port,
                target_port=extra_port,
                protocol="TCP"
            ))
        
        service_manifest = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=resource_name,
                namespace=self.NAMESPACE,
                labels={
                    "app": "e-claw",
                    "resource-name": resource_name
                }
            ),
            spec=client.V1ServiceSpec(
                selector={
                    "app": "e-claw",
                    "resource-name": resource_name
                },
                ports=ports,
                type="ClusterIP"
            )
        )
        
        try:
            self.core_v1.create_namespaced_service(
                namespace=self.NAMESPACE,
                body=service_manifest
            )
            return {"status": "created", "service_name": resource_name}
        except ApiException as e:
            if e.status == 409:  # Already exists
                return {"status": "exists", "service_name": resource_name}
            return {"error": str(e)}
    
    async def cleanup_resources(self, resource_name: str) -> Dict[str, Any]:
        """清理所有资源（PVC, Pod, Service）"""
        errors = []
        
        # 删除Service
        try:
            self.core_v1.delete_namespaced_service(
                name=resource_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except Exception as e:
            errors.append(f"Service: {str(e)}")
        
        # 删除Pod
        try:
            self.apps_v1.delete_namespaced_pod(
                name=resource_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except Exception as e:
            errors.append(f"Pod: {str(e)}")
        
        # 删除PVC
        try:
            pvc_name = f"{resource_name}-data"
            self.core_v1.delete_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
        except Exception as e:
            errors.append(f"PVC: {str(e)}")
        
        if errors:
            return {"status": "partial", "errors": errors}
        return {"status": "cleaned"}
    
    async def delete_pvc(self, resource_name: str) -> Dict[str, Any]:
        """删除PVC"""
        try:
            pvc_name = f"{resource_name}-data"
            self.core_v1.delete_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=self.NAMESPACE,
                body=client.V1DeleteOptions()
            )
            return {"status": "deleted", "pvc_name": pvc_name}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_pod_info(self, resource_name: str) -> Dict[str, Any]:
        """获取Pod详细信息"""
        try:
            pod = self.apps_v1.read_namespaced_pod(
                name=resource_name,
                namespace=self.NAMESPACE
            )
            return {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "pod_ip": pod.status.pod_ip,
                "host_ip": pod.status.host_ip,
                "node_name": pod.spec.node_name,
                "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                "labels": pod.metadata.labels
            }
        except ApiException as e:
            return {"error": str(e)}
    
    async def list_pods_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用户的所有Pod"""
        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=self.NAMESPACE,
                label_selector=f"user-id={user_id}"
            )
            
            result = []
            for pod in pods.items:
                result.append({
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "pod_ip": pod.status.pod_ip,
                    "created": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
                })
            return result
        except ApiException:
            return []


# 全局K8s服务实例
k8s_service = K8sService()