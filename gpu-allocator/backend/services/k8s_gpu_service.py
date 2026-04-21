"""
K8s GPU资源服务
从Kubernetes集群获取GPU卡信息
"""
import os
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# K8s配置模式
K8S_MODE = os.getenv("K8S_MODE", "mock")  # auto, in_cluster, mock

class K8sGPUService:
    """K8s GPU资源服务类"""
    
    def __init__(self):
        self.k8s_client = None
        self._init_client()
    
    def _init_client(self):
        """初始化K8s客户端"""
        if K8S_MODE == "mock":
            logger.info("K8s模式: Mock (模拟数据)")
            return
        
        try:
            from kubernetes import client, config
            from kubernetes.client.rest import ApiException
            
            # 尝试加载K8s配置
            try:
                # 尝试使用Pod内配置
                config.load_incluster_config()
                logger.info("已加载K8s InCluster配置")
            except Exception:
                # 尝试使用本地kubeconfig
                try:
                    config.load_kube_config()
                    logger.info("已加载K8s kubeconfig配置")
                except Exception:
                    logger.warning("无法加载K8s配置，将使用模拟数据")
                    return
            
            self.k8s_client = client.CoreV1Api()
            self.api_exception = ApiException
            logger.info("K8s客户端初始化成功")
            
        except ImportError:
            logger.warning("kubernetes包未安装，将使用模拟数据")
        except Exception as e:
            logger.warning(f"K8s客户端初始化失败: {e}，将使用模拟数据")
    
    def get_gpu_nodes(self) -> List[dict]:
        """获取所有GPU节点"""
        if K8S_MODE == "mock" or self.k8s_client is None:
            return self._get_mock_gpu_nodes()
        
        try:
            # 获取所有节点
            nodes = self.k8s_client.list_node().items
            gpu_nodes = []
            
            for node in nodes:
                # 检查节点是否有GPU
                allocatable = node.status.allocatable
                if not allocatable:
                    continue
                
                # 检查nvidia.com/gpu资源
                gpu_count = allocatable.get('nvidia.com/gpu', '0')
                if gpu_count == '0' or gpu_count is None:
                    continue
                
                # 获取节点信息
                node_name = node.metadata.name
                labels = node.metadata.labels or {}
                
                # 获取节点上的GPU信息
                node_gpus = self._get_node_gpu_info(node)
                
                gpu_nodes.extend(node_gpus)
            
            return gpu_nodes
            
        except Exception as e:
            logger.error(f"获取K8s GPU节点失败: {e}")
            return self._get_mock_gpu_nodes()
    
    def _get_node_gpu_info(self, node) -> List[dict]:
        """获取单个节点的GPU详细信息"""
        gpu_info_list = []
        
        try:
            # 获取节点名称和GPU数量
            node_name = node.metadata.name
            allocatable = node.status.allocatable
            gpu_count = int(allocatable.get('nvidia.com/gpu', '0'))
            
            # 获取节点注解中的GPU信息
            annotations = node.metadata.annotations or {}
            
            # 尝试从注解中获取GPU型号
            gpu_model = annotations.get('nvidia.com/gpu.model', 'NVIDIA GPU')
            
            # 获取节点容量
            capacity = node.status.capacity
            memory = capacity.get('memory', '0Ki')
            memory_mb = self._parse_memory_to_mb(memory)
            
            # 为每个GPU创建条目
            for i in range(gpu_count):
                gpu_info = {
                    'id': f'{node_name}-gpu-{i}',
                    'name': f'{gpu_model}',
                    'node': node_name,
                    'index': i,
                    'total_memory': memory_mb // gpu_count if gpu_count > 0 else memory_mb,
                    'used_memory': 0,
                    'status': 'available',
                    'assigned_app': None,
                }
                gpu_info_list.append(gpu_info)
                
        except Exception as e:
            logger.error(f"获取节点GPU信息失败: {e}")
        
        return gpu_info_list
    
    def _parse_memory_to_mb(self, memory_str: str) -> int:
        """将Kubernetes内存格式转换为MB"""
        try:
            # 移除可能的空格
            memory_str = memory_str.strip()
            
            if memory_str.endswith('Ki'):
                return int(memory_str[:-2]) // 1024
            elif memory_str.endswith('Mi'):
                return int(memory_str[:-2])
            elif memory_str.endswith('Gi'):
                return int(memory_str[:-2]) * 1024
            elif memory_str.endswith('Ti'):
                return int(memory_str[:-2]) * 1024 * 1024
            else:
                # 假设是Ki
                return int(memory_str) // 1024
        except:
            return 8192  # 默认8GB
    
    def _get_mock_gpu_nodes(self) -> List[dict]:
        """获取模拟GPU节点数据（用于测试或无K8s环境）"""
        return [
            {'id': 'gpu-0', 'name': 'NVIDIA A100-40GB', 'node': 'k8s-node-1', 'index': 0, 'total_memory': 40960, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-1', 'name': 'NVIDIA A100-40GB', 'node': 'k8s-node-1', 'index': 1, 'total_memory': 40960, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-2', 'name': 'NVIDIA A100-40GB', 'node': 'k8s-node-2', 'index': 0, 'total_memory': 40960, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-3', 'name': 'NVIDIA A100-40GB', 'node': 'k8s-node-2', 'index': 1, 'total_memory': 40960, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-4', 'name': 'NVIDIA RTX 4090', 'node': 'k8s-node-3', 'index': 0, 'total_memory': 24576, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-5', 'name': 'NVIDIA RTX 4090', 'node': 'k8s-node-3', 'index': 1, 'total_memory': 24576, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-6', 'name': 'NVIDIA RTX 4090', 'node': 'k8s-node-4', 'index': 0, 'total_memory': 24576, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
            {'id': 'gpu-7', 'name': 'NVIDIA RTX 4090', 'node': 'k8s-node-4', 'index': 1, 'total_memory': 24576, 'used_memory': 0, 'status': 'available', 'assigned_app': None},
        ]
    
    def get_pods_with_gpu(self) -> List[dict]:
        """获取使用GPU的Pod列表"""
        if K8S_MODE == "mock" or self.k8s_client is None:
            return []
        
        try:
            pods = self.k8s_client.list_pod_for_all_namespaces().items
            gpu_pods = []
            
            for pod in pods:
                # 检查Pod是否请求了GPU
                containers = pod.spec.containers
                for container in containers:
                    resources = container.resources
                    if resources and resources.limits:
                        if 'nvidia.com/gpu' in resources.limits:
                            gpu_pods.append({
                                'name': pod.metadata.name,
                                'namespace': pod.metadata.namespace,
                                'node': pod.spec.node_name,
                                'gpu_request': resources.limits.get('nvidia.com/gpu', '0'),
                                'status': pod.status.phase,
                            })
            
            return gpu_pods
            
        except Exception as e:
            logger.error(f"获取GPU Pod列表失败: {e}")
            return []
    
    def refresh_gpu_status(self, current_gpus: List[dict]) -> List[dict]:
        """刷新GPU状态（从K8s获取最新状态）"""
        k8s_gpus = self.get_gpu_nodes()
        
        # 合并状态
        for gpu in current_gpus:
            for k8s_gpu in k8s_gpus:
                if gpu['id'] == k8s_gpu['id']:
                    # 更新状态
                    gpu['status'] = k8s_gpu.get('status', 'available')
                    gpu['used_memory'] = k8s_gpu.get('used_memory', 0)
                    break
        
        return current_gpus


# 全局服务实例
k8s_gpu_service = K8sGPUService()