"""
Slurm分布式作业管理系统
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
import queue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JobState(Enum):
    """作业状态枚举"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    NODE_OFFLINE = "NODE_OFFLINE"
    UNKNOWN = "UNKNOWN"


class JobPriority(Enum):
    """作业优先级"""
    LOW = 1
    NORMAL = 50
    HIGH = 100
    URGENT = 150


@dataclass
class SlurmJob:
    """Slurm作业定义"""
    job_id: str = ""
    name: str = ""
    script: str = ""
    script_content: str = ""
    
    # 资源需求
    num_nodes: int = 1
    num_tasks: int = 1
    cpus_per_task: int = 1
    mem_per_node: str = "1G"
    gpus: int = 0
    gpu_type: str = ""
    
    # 时间限制
    time_limit: str = "01:00:00"
    
    # 队列和分区
    partition: str = "default"
    qos: str = ""
    
    # 依赖
    dependency: str = ""
    
    # 环境变量
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # 约束
    constraints: str = ""
    
    # 输出
    output: str = "/tmp/slurm_%j.out"
    error: str = ""
    
    # 状态
    state: JobState = JobState.UNKNOWN
    state_reason: str = ""
    submit_time: datetime = field(default_factory=datetime.now)
    start_time: datetime = None
    end_time: datetime = None
    
    # 节点信息
    node_list: str = ""
    
    # 进度
    progress: float = 0.0
    
    def to_sbatch(self) -> str:
        """转换为sbatch脚本"""
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={self.name}",
            f"#SBATCH --output={self.output}",
        ]
        
        if self.error:
            lines.append(f"#SBATCH --error={self.error}")
        
        lines.extend([
            f"#SBATCH --nodes={self.num_nodes}",
            f"#SBATCH --ntasks={self.num_tasks}",
            f"#SBATCH --cpus-per-task={self.cpus_per_task}",
            f"#SBATCH --mem={self.mem_per_node}",
            f"#SBATCH --time={self.time_limit}",
            f"#SBATCH --partition={self.partition}",
        ])
        
        if self.gpus > 0:
            if self.gpu_type:
                lines.append(f"#SBATCH --gres=gpu:{self.gpu_type}:{self.gpus}")
            else:
                lines.append(f"#SBATCH --gres=gpu:{self.gpus}")
        
        if self.qos:
            lines.append(f"#SBATCH --qos={self.qos}")
        
        if self.dependency:
            lines.append(f"#SBATCH --dependency={self.dependency}")
        
        if self.constraints:
            lines.append(f"#SBATCH --constraint={self.constraints}")
        
        if self.env_vars:
            for key, value in self.env_vars.items():
                lines.append(f"export {key}={value}")
        
        lines.append("")
        
        if self.script_content:
            lines.append(self.script_content)
        elif self.script:
            lines.append(f"{self.script}")
        
        return "\n".join(lines)


@dataclass
class NodeInfo:
    """节点信息"""
    name: str
    state: str
    cpus: int = 0
    mem_total: int = 0
    mem_free: int = 0
    gpus: int = 0
    gpus_free: int = 0
    partitions: List[str] = field(default_factory=list)
    
    @property
    def available(self) -> bool:
        return self.state == "IDLE" or self.state == "ALLOCATED"


@dataclass
class PartitionInfo:
    """分区信息"""
    name: str
    state: str
    nodes: int = 0
    nodes_free: int = 0
    total_cpus: int = 0
    total_mem: int = 0


class SlurmClient:
    """Slurm客户端封装"""
    
    def __init__(self, slurm_path: str = "sbatch"):
        self.slurm_path = slurm_path
        self._check_connection()
    
    def _check_connection(self):
        """检查Slurm连接"""
        try:
            result = subprocess.run(
                ["sinfo", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("Slurm连接正常")
            else:
                logger.warning("Slurm命令执行异常")
        except FileNotFoundError:
            logger.warning("Slurm命令未找到，模拟模式")
        except Exception as e:
            logger.warning(f"Slurm连接检查失败: {e}")
    
    def submit_job(self, job: SlurmJob) -> str:
        """提交作业"""
        script = job.to_sbatch()
        
        try:
            result = subprocess.run(
                ["sbatch"],
                input=script,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                job_id = output.replace("Submitted batch job ", "")
                job.job_id = job_id
                logger.info(f"作业提交成功: {job_id}")
                return job_id
            else:
                logger.error(f"作业提交失败: {result.stderr}")
                raise RuntimeError(f"提交失败: {result.stderr}")
                
        except FileNotFoundError:
            logger.warning("sbatch命令未找到，使用模拟模式")
            job_id = f"mock_{int(time.time())}"
            job.job_id = job_id
            return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        try:
            result = subprocess.run(
                ["scancel", job_id],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"取消作业失败: {e}")
            return False
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """获取作业状态"""
        try:
            result = subprocess.run(
                ["scontrol", "show", f"jobid={job_id}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return self._parse_job_info(result.stdout)
            else:
                return {"state": "NOT_FOUND", "state_reason": result.stderr}
        except Exception as e:
            logger.error(f"获取作业状态失败: {e}")
            return {"state": "UNKNOWN"}
    
    def _parse_job_info(self, output: str) -> Dict[str, Any]:
        """解析scontrol输出"""
        info = {}
        for line in output.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                info[key.strip()] = value.strip()
        return info
    
    def list_jobs(self, user: str = "") -> List[Dict[str, Any]]:
        """列出作业"""
        cmd = ["squeue", "-o", "%.18i %.9P %.20j %.8u %.2t %.10M %.6D %R"]
        if user:
            cmd.extend(["-u", user])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                jobs = []
                lines = result.stdout.strip().split("\n")[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 8:
                        jobs.append({
                            "job_id": parts[0],
                            "partition": parts[1],
                            "name": parts[2],
                            "user": parts[3],
                            "state": parts[4],
                            "time": parts[5],
                            "nodes": parts[6],
                            "node": parts[7] if len(parts) > 7 else ""
                        })
                return jobs
        except Exception as e:
            logger.error(f"列出作业失败: {e}")
        return []
    
    def get_nodes(self) -> List[NodeInfo]:
        """获取节点列表"""
        try:
            result = subprocess.run(
                ["sinfo", "-o", "%n %T %c %m %m %G"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                nodes = []
                lines = result.stdout.strip().split("\n")[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        nodes.append(NodeInfo(
                            name=parts[0],
                            state=parts[1],
                            cpus=int(parts[2]),
                            mem_total=self._parse_mem(parts[3]) if len(parts) > 3 else 0
                        ))
                return nodes
        except Exception as e:
            logger.error(f"获取节点失败: {e}")
        return []
    
    def get_partitions(self) -> List[PartitionInfo]:
        """获取分区列表"""
        try:
            result = subprocess.run(
                ["sinfo", "-o", "%P %T %N %H"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                partitions = []
                lines = result.stdout.strip().split("\n")[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        partitions.append(PartitionInfo(
                            name=parts[0],
                            state=parts[1]
                        ))
                return partitions
        except Exception as e:
            logger.error(f"获取分区失败: {e}")
        return []
    
    def _parse_mem(self, mem_str: str) -> int:
        """解析内存字符串"""
        try:
            if "T" in mem_str:
                return int(mem_str.replace("T", "")) * 1024 * 1024
            elif "G" in mem_str:
                return int(mem_str.replace("G", "")) * 1024 * 1024
            elif "M" in mem_str:
                return int(mem_str.replace("M", ""))
            return int(mem_str)
        except:
            return 0


class JobScheduler:
    """作业调度器"""
    
    def __init__(self, client: SlurmClient):
        self.client = client
        self.jobs: Dict[str, SlurmJob] = {}
        self.job_queue = queue.Queue()
        self.running = False
        self._lock = threading.Lock()
    
    def add_job(self, job: SlurmJob) -> str:
        """添加作业到队列"""
        with self._lock:
            job_id = self.client.submit_job(job)
            self.jobs[job_id] = job
            logger.info(f"作业 {job_id} 已添加到调度器")
            return job_id
    
    def submit_array_job(self, array_spec: str, job: SlurmJob) -> str:
        """提交数组作业"""
        job.dependency = f"array={array_spec}"
        return self.add_job(job)
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        with self._lock:
            if job_id in self.jobs:
                result = self.client.cancel_job(job_id)
                if result:
                    self.jobs[job_id].state = JobState.CANCELLED
                return result
        return False
    
    def get_job(self, job_id: str) -> Optional[SlurmJob]:
        """获取作业信息"""
        with self._lock:
            return self.jobs.get(job_id)
    
    def list_jobs(self) -> List[SlurmJob]:
        """列出所有作业"""
        with self._lock:
            return list(self.jobs.values())
    
    def wait_for_job(self, job_id: str, timeout: int = 3600) -> JobState:
        """等待作业完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.client.get_job_status(job_id)
            state = status.get("JobState", "UNKNOWN")
            
            job_state = self._convert_state(state)
            
            if job_state in [JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED]:
                with self._lock:
                    if job_id in self.jobs:
                        self.jobs[job_id].state = job_state
                return job_state
            
            time.sleep(5)
        
        return JobState.TIMEOUT
    
    def _convert_state(self, state: str) -> JobState:
        """转换状态"""
        state_map = {
            "PENDING": JobState.PENDING,
            "RUNNING": JobState.RUNNING,
            "COMPLETED": JobState.COMPLETED,
            "FAILED": JobState.FAILED,
            "CANCELLED": JobState.CANCELLED,
            "TIMEOUT": JobState.TIMEOUT,
            "NODE_FAIL": JobState.NODE_OFFLINE,
        }
        return state_map.get(state.upper(), JobState.UNKNOWN)


class JobMonitor:
    """作业监控器"""
    
    def __init__(self, scheduler: JobScheduler, check_interval: int = 30):
        self.scheduler = scheduler
        self.check_interval = check_interval
        self.running = False
        self._lock = threading.Lock()
        self._thread = None
        self._callbacks: List[callable] = []
    
    def start(self):
        """启动监控"""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._monitor_loop)
            self._thread.daemon = True
            self._thread.start()
            logger.info("作业监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("作业监控已停止")
    
    def add_callback(self, callback: callable):
        """添加状态变化回调"""
        self._callbacks.append(callback)
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            self._check_jobs()
            time.sleep(self.check_interval)
    
    def _check_jobs(self):
        """检查所有作业状态"""
        with self._lock:
            jobs = self.scheduler.list_jobs()
        
        for job in jobs:
            if job.job_id and job.state in [JobState.PENDING, JobState.RUNNING]:
                status = self.scheduler.client.get_job_status(job.job_id)
                old_state = job.state
                
                state_str = status.get("JobState", "UNKNOWN")
                job.state = self.scheduler._convert_state(state_str)
                job.state_reason = status.get("StateReason", "")
                job.node_list = status.get("NodeList", "")
                
                if old_state != job.state:
                    for callback in self._callbacks:
                        try:
                            callback(job)
                        except Exception as e:
                            logger.error(f"回调执行失败: {e}")
    
    def get_statistics(self) -> Dict[str, int]:
        """获取作业统计"""
        stats = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 0
        }
        
        with self._lock:
            jobs = self.scheduler.list_jobs()
        
        stats["total"] = len(jobs)
        
        for job in jobs:
            if job.state == JobState.PENDING:
                stats["pending"] += 1
            elif job.state == JobState.RUNNING:
                stats["running"] += 1
            elif job.state == JobState.COMPLETED:
                stats["completed"] += 1
            elif job.state == JobState.FAILED:
                stats["failed"] += 1
            elif job.state == JobState.CANCELLED:
                stats["cancelled"] += 1
        
        return stats


class DistributedJobManager:
    """分布式作业管理器 - 主入口"""
    
    def __init__(self, slurm_path: str = "sbatch"):
        self.client = SlurmClient(slurm_path)
        self.scheduler = JobScheduler(self.client)
        self.monitor = JobMonitor(self.scheduler)
        self.monitor.start()
        logger.info("分布式作业管理器已初始化")
    
    def submit_job(
        self,
        name: str,
        script: str,
        num_nodes: int = 1,
        cpus_per_task: int = 1,
        mem: str = "1G",
        gpus: int = 0,
        partition: str = "default",
        time_limit: str = "01:00:00",
        **kwargs
    ) -> str:
        """提交作业"""
        job = SlurmJob(
            name=name,
            script=script,
            num_nodes=num_nodes,
            cpus_per_task=cpus_per_task,
            mem_per_node=mem,
            gpus=gpus,
            partition=partition,
            time_limit=time_limit,
            **kwargs
        )
        return self.scheduler.add_job(job)
    
    def submit_script(
        self,
        name: str,
        script_content: str,
        **kwargs
    ) -> str:
        """提交脚本内容"""
        job = SlurmJob(
            name=name,
            script_content=script_content,
            **kwargs
        )
        return self.scheduler.add_job(job)
    
    def submit_array(
        self,
        name: str,
        script: str,
        start: int,
        end: int,
        step: int = 1
    ) -> str:
        """提交数组作业"""
        array_spec = f"{start}-{end}:{step}"
        job = SlurmJob(
            name=name,
            script=script,
            output=f"/tmp/slurm_{name}_%A_%a.out"
        )
        return self.scheduler.submit_array_job(array_spec, job)
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        return self.scheduler.cancel_job(job_id)
    
    def get_job(self, job_id: str) -> Optional[SlurmJob]:
        """获取作业信息"""
        return self.scheduler.get_job(job_id)
    
    def list_jobs(self) -> List[SlurmJob]:
        """列出所有作业"""
        return self.scheduler.list_jobs()
    
    def wait_job(self, job_id: str, timeout: int = 3600) -> JobState:
        """等待作业完成"""
        return self.scheduler.wait_for_job(job_id, timeout)
    
    def get_statistics(self) -> Dict[str, int]:
        """获取作业统计"""
        return self.monitor.get_statistics()
    
    def get_node_info(self) -> List[NodeInfo]:
        """获取节点信息"""
        return self.client.get_nodes()
    
    def get_partition_info(self) -> List[PartitionInfo]:
        """获取分区信息"""
        return self.client.get_partitions()
    
    def add_job_callback(self, callback: callable):
        """添加作业状态变化回调"""
        self.monitor.add_callback(callback)
    
    def shutdown(self):
        """关闭管理器"""
        self.monitor.stop()
        logger.info("分布式作业管理器已关闭")


def demo():
    """演示"""
    print("=" * 50)
    print("Slurm分布式作业管理系统演示")
    print("=" * 50)
    
    # 创建管理器
    manager = DistributedJobManager()
    
    # 提交作业
    job_id = manager.submit_job(
        name="test_job",
        script="echo 'Hello, Slurm!'",
        num_nodes=1,
        cpus_per_task=2,
        mem="2G",
        partition="default",
        time_limit="00:10:00"
    )
    print(f"提交作业: {job_id}")
    
    # 提交脚本
    script = """#!/bin/bash
echo "Job started at $(date)"
sleep 5
echo "Job finished at $(date)"
"""
    job_id2 = manager.submit_script(
        name="script_job",
        script_content=script,
        cpus_per_task=4,
        mem_per_node="4G"
    )
    print(f"提交脚本作业: {job_id2}")
    
    # 列出作业
    jobs = manager.list_jobs()
    print(f"\n当前作业数: {len(jobs)}")
    
    # 获取统计
    stats = manager.get_statistics()
    print(f"作业统计: {stats}")
    
    # 获取节点信息
    nodes = manager.get_node_info()
    print(f"节点数: {len(nodes)}")
    
    # 清理
    manager.shutdown()
    print("\n演示完成")


if __name__ == "__main__":
    demo()