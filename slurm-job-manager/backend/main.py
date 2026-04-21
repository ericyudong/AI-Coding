"""
Slurm作业管理系统后端
提供RESTful API用于作业管理
"""
import sys
import os
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import subprocess

# 添加父目录到路径以便导入slurm_job_manager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入Slurm作业管理器，如果失败则使用直接调用sinfo的方式
try:
    from slurm_job_manager import (
        SlurmJob, SlurmClient, JobScheduler, JobMonitor, 
        DistributedJobManager, JobState, JobPriority, NodeInfo, PartitionInfo
    )
    MANAGER = DistributedJobManager()
    logger.info("Slurm作业管理器初始化成功")
except Exception as e:
    logger.warning(f"Slurm管理器初始化失败，使用直接调用模式: {e}")
    MANAGER = None

app = FastAPI(title="Slurm作业管理系统", version="1.0.0")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局节点存储（用于存储用户添加的节点）
custom_nodes: List[NodeResponse] = []


# ============ 数据模型 ============

class JobStateEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    NODE_OFFLINE = "NODE_OFFLINE"
    UNKNOWN = "UNKNOWN"


class JobSubmitRequest(BaseModel):
    name: str
    script: str = ""
    script_content: str = ""
    num_nodes: int = 1
    num_tasks: int = 1
    cpus_per_task: int = 1
    mem_per_node: str = "1G"
    gpus: int = 0
    gpu_type: str = ""
    time_limit: str = "01:00:00"
    partition: str = "default"
    qos: str = ""
    output: str = "/tmp/slurm_%j.out"


class JobResponse(BaseModel):
    job_id: str
    name: str
    state: str
    partition: str
    num_nodes: int
    num_tasks: int
    cpus_per_task: int
    mem_per_node: str
    gpus: int
    time_limit: str
    submit_time: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    node_list: str = ""
    progress: float = 0.0


class NodeResponse(BaseModel):
    name: str
    state: str
    cpus: int = 0
    mem_total: int = 0
    mem_free: int = 0
    gpus: int = 0
    gpus_free: int = 0
    partitions: List[str] = []
    available: bool = True


class PartitionResponse(BaseModel):
    name: str
    state: str
    nodes: int = 0
    nodes_free: int = 0
    total_cpus: int = 0
    total_mem: int = 0


class StatisticsResponse(BaseModel):
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    total: int


def run_wsl_command(cmd: List[str]) -> str:
    """运行WSL命令并返回输出"""
    try:
        # 使用wsl命令执行sinfo等
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu"] + cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        logger.error(f"WSL命令执行失败: {e}")
        return ""


def get_nodes_from_slurm() -> List[NodeResponse]:
    """直接从Slurm获取节点信息 - 使用scontrol替代sinfo"""
    try:
        # 首先尝试使用sinfo
        output = run_wsl_command(["sinfo", "-o", "%n %T %c %m %m %G"])
        
        # 如果sinfo有有效输出，解析它
        if output and "HOSTNAMES" not in output.split("\n")[0]:
            lines = output.strip().split("\n")
            nodes = []
            for line in lines[1:]:  # 跳过标题行
                parts = line.split()
                if len(parts) >= 2:
                    node = NodeResponse(
                        name=parts[0],
                        state=parts[1],
                        cpus=int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 4,
                        mem_total=int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 8192,
                        mem_free=int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 4096,
                        gpus=0,
                        gpus_free=0,
                        partitions=["default"],
                        available=parts[1].lower() in ["idle", "mixed", "allocated", "down"]
                    )
                    nodes.append(node)
            if nodes:
                return nodes
        
        # 如果sinfo失败或没有数据，尝试使用scontrol
        output = run_wsl_command(["scontrol", "show", "node", "-a"])
        if output and "NodeName" in output:
            nodes = []
            # 处理scontrol输出 - 每两行一个节点
            # 格式: NodeName=xxx ...\n   key=value key=value ...
            lines = output.strip().split("\n")
            node_info = {}
            node_name = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    # 空行表示新节点开始，保存之前的节点
                    if node_name and node_info:
                        nodes.append(_parse_scontrol_node(node_name, node_info))
                    node_info = {}
                    node_name = None
                    continue
                
                # 解析 key=value 对，处理没有空格的情况
                # 例如: "NodeName=localhost CoresPerSocket=1" 或 "NodeAddr=localhost"
                parts = line.replace("   ", " ").split()
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == "NodeName":
                            # 处理第一个字段后面可能跟着其他属性
                            # 例如: "NodeName=localhost CoresPerSocket=1"
                            node_name = value.split()[0] if value else value
                        else:
                            node_info[key] = value
            
            # 处理最后一个节点
            if node_name and node_info:
                nodes.append(_parse_scontrol_node(node_name, node_info))
            
            if nodes:
                return nodes
        
        # 如果都没有数据，返回演示数据
        return get_demo_nodes()
        
    except Exception as e:
        logger.error(f"获取节点信息失败: {e}")
        return get_demo_nodes()


def _parse_scontrol_node(node_name: str, node_info: Dict[str, str]) -> NodeResponse:
    """解析scontrol输出中的节点信息"""
    # 解析CPU和内存信息
    cpus = 1
    mem_total = 8192
    mem_free = 4096
    
    if "CPUTot" in node_info:
        try:
            cpus = int(node_info["CPUTot"])
        except:
            pass
    
    if "RealMemory" in node_info:
        try:
            mem_total = int(node_info["RealMemory"])
            # 如果内存值太小（小于100MB），说明不是真实数据，使用系统内存
            if mem_total < 100:
                mem_total, mem_free = get_system_memory()
            else:
                mem_free = mem_total  # 简化处理
        except:
            # 获取系统内存作为后备
            mem_total, mem_free = get_system_memory()
    else:
        # 没有RealMemory信息，尝试获取系统内存
        mem_total, mem_free = get_system_memory()
    
    # 解析状态
    state = node_info.get("State", "UNKNOWN").split("+")[0].lower()
    
    return NodeResponse(
        name=node_name,
        state=state,
        cpus=cpus,
        mem_total=mem_total,
        mem_free=mem_free,
        gpus=0,
        gpus_free=0,
        partitions=["default"],
        available=state in ["idle", "mixed", "allocated", "down"]
    )


def get_system_memory() -> tuple:
    """获取系统内存信息（总内存和可用内存），单位MB"""
    try:
        # Windows 上使用 wmic 获取内存
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "-e", "free", "-m"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        total = int(parts[1])
                        if len(parts) >= 7:
                            free = int(parts[6])
                        else:
                            free = total // 2
                        return total, free
    except Exception as e:
        logger.warning(f"获取系统内存失败: {e}")
    
    # 默认返回 8GB
    return 8192, 4096


def get_demo_nodes() -> List[NodeResponse]:
    """返回演示节点数据"""
    return [
        NodeResponse(
            name="gpu-node-1",
            state="idle",
            cpus=32,
            mem_total=128000,
            mem_free=64000,
            gpus=4,
            gpus_free=4,
            partitions=["default", "gpu"],
            available=True
        ),
        NodeResponse(
            name="gpu-node-2",
            state="allocated",
            cpus=32,
            mem_total=128000,
            mem_free=32000,
            gpus=4,
            gpus_free=0,
            partitions=["default", "gpu"],
            available=True
        ),
        NodeResponse(
            name="cpu-node-1",
            state="idle",
            cpus=64,
            mem_total=256000,
            mem_free=128000,
            gpus=0,
            gpus_free=0,
            partitions=["default", "cpu"],
            available=True
        ),
        NodeResponse(
            name="cpu-node-2",
            state="idle",
            cpus=64,
            mem_total=256000,
            mem_free=256000,
            gpus=0,
            gpus_free=0,
            partitions=["default", "cpu"],
            available=True
        )
    ]


# ============ API端点 ============

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "Slurm作业管理系统API",
        "version": "1.0.0",
        "manager_status": "active" if MANAGER else "wsl_direct"
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "manager": "active" if MANAGER else "wsl_direct"}


@app.get("/api/jobs", response_model=List[JobResponse])
async def list_jobs():
    """获取所有作业列表"""
    if MANAGER:
        jobs = MANAGER.list_jobs()
        return [job_to_response(job) for job in jobs]
    
    # 从squeue获取作业
    try:
        output = run_wsl_command(["squeue", "-o", "%.18i %.9P %.20j %.8u %.2t %.10M %.6D %R"])
        
        # 如果没有作业，返回模拟数据
        if not output or "NO JOBS" in output:
            return get_demo_jobs()
        
        jobs = []
        lines = output.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 5:
                jobs.append(JobResponse(
                    job_id=parts[0],
                    name=parts[2],
                    state=parts[4],
                    partition=parts[1],
                    num_nodes=int(parts[6]) if len(parts) > 6 else 1,
                    num_tasks=1,
                    cpus_per_task=1,
                    mem_per_node="1G",
                    gpus=0,
                    time_limit=parts[5] if len(parts) > 5 else "00:00:00",
                    submit_time=datetime.now().isoformat()
                ))
        return jobs
    except Exception as e:
        logger.error(f"获取作业失败: {e}")
        return get_demo_jobs()


def get_demo_jobs() -> List[JobResponse]:
    """返回演示作业数据"""
    return [
        JobResponse(
            job_id="1001",
            name="training-job-1",
            state="RUNNING",
            partition="gpu",
            num_nodes=1,
            num_tasks=4,
            cpus_per_task=8,
            mem_per_node="32G",
            gpus=4,
            time_limit="04:00:00",
            submit_time=datetime.now().isoformat(),
            start_time=datetime.now().isoformat(),
            node_list="gpu-node-2",
            progress=45.5
        ),
        JobResponse(
            job_id="1002",
            name="inference-job-1",
            state="PENDING",
            partition="gpu",
            num_nodes=1,
            num_tasks=2,
            cpus_per_task=4,
            mem_per_node="16G",
            gpus=2,
            time_limit="01:00:00",
            submit_time=datetime.now().isoformat(),
            progress=0.0
        ),
        JobResponse(
            job_id="1003",
            name="data-processing",
            state="PENDING",
            partition="cpu",
            num_nodes=2,
            num_tasks=16,
            cpus_per_task=4,
            mem_per_node="16G",
            gpus=0,
            time_limit="02:00:00",
            submit_time=datetime.now().isoformat(),
            progress=0.0
        )
    ]


def job_to_response(job) -> JobResponse:
    """将SlurmJob转换为API响应"""
    return JobResponse(
        job_id=job.job_id,
        name=job.name,
        state=job.state.value if hasattr(job.state, 'value') else str(job.state),
        partition=job.partition,
        num_nodes=job.num_nodes,
        num_tasks=job.num_tasks,
        cpus_per_task=job.cpus_per_task,
        mem_per_node=job.mem_per_node,
        gpus=job.gpus,
        time_limit=job.time_limit,
        submit_time=job.submit_time.isoformat() if hasattr(job.submit_time, 'isoformat') else str(job.submit_time),
        start_time=job.start_time.isoformat() if job.start_time and hasattr(job.start_time, 'isoformat') else None,
        end_time=job.end_time.isoformat() if job.end_time and hasattr(job.end_time, 'isoformat') else None,
        node_list=job.node_list,
        progress=job.progress
    )


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """获取指定作业详情"""
    if not MANAGER:
        # 从scontrol获取
        output = run_wsl_command(["scontrol", "show", f"jobid={job_id}"])
        if not output:
            raise HTTPException(status_code=404, detail="作业不存在")
        
        # 简单解析
        return JobResponse(
            job_id=job_id,
            name="Unknown",
            state="UNKNOWN",
            partition="default",
            num_nodes=1,
            num_tasks=1,
            cpus_per_task=1,
            mem_per_node="1G",
            gpus=0,
            time_limit="01:00:00",
            submit_time=datetime.now().isoformat()
        )
    
    job = MANAGER.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    return job_to_response(job)


@app.post("/api/jobs", response_model=JobResponse)
async def submit_job(request: JobSubmitRequest):
    """提交新作业"""
    try:
        # 写入临时脚本文件
        script_content = request.script_content or f"#!/bin/bash\n{request.script}"
        
        # 通过WSL提交作业
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "sbatch"],
            input=script_content,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            job_id = result.stdout.strip().replace("Submitted batch job ", "")
            return JobResponse(
                job_id=job_id,
                name=request.name,
                state="PENDING",
                partition=request.partition,
                num_nodes=request.num_nodes,
                num_tasks=request.num_tasks,
                cpus_per_task=request.cpus_per_task,
                mem_per_node=request.mem_per_node,
                gpus=request.gpus,
                time_limit=request.time_limit,
                submit_time=datetime.now().isoformat()
            )
        else:
            raise HTTPException(status_code=500, detail=f"提交失败: {result.stderr}")
            
    except Exception as e:
        logger.error(f"提交作业失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """取消作业"""
    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "scancel", job_id],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return {"message": f"作业 {job_id} 已取消", "success": True}
        else:
            raise HTTPException(status_code=400, detail=f"取消失败: {result.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """获取作业统计"""
    if MANAGER:
        stats = MANAGER.get_statistics()
        return StatisticsResponse(**stats)
    
    # 从squeue统计
    try:
        output = run_wsl_command(["squeue", "-o", "%T"])
        
        # 如果没有作业，返回演示数据
        if not output or "NO JOBS" in output:
            return StatisticsResponse(
                pending=2, running=1, completed=0, 
                failed=0, cancelled=0, total=3
            )
        
        stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0, "total": 0}
        
        lines = output.strip().split("\n")
        for line in lines[1:]:
            state = line.strip()
            stats["total"] += 1
            if state == "PENDING":
                stats["pending"] += 1
            elif state == "RUNNING":
                stats["running"] += 1
            elif state == "COMPLETED":
                stats["completed"] += 1
            elif state == "FAILED":
                stats["failed"] += 1
            elif state == "CANCELLED":
                stats["cancelled"] += 1
        
        return StatisticsResponse(**stats)
    except Exception as e:
        return StatisticsResponse(
            pending=2, running=1, completed=0, 
            failed=0, cancelled=0, total=3
        )


class NodeCreateRequest(BaseModel):
    name: str
    cpus: int = 4
    mem_total: int = 8192
    gpus: int = 0
    partitions: List[str] = ["default"]


@app.get("/api/nodes", response_model=List[NodeResponse])
async def list_nodes():
    """获取节点列表（包含自定义节点）"""
    # 获取Slurm节点
    slurm_nodes = get_nodes_from_slurm()
    # 合并自定义节点
    all_nodes = slurm_nodes + custom_nodes
    return all_nodes


@app.post("/api/nodes", response_model=NodeResponse)
async def create_node(request: NodeCreateRequest):
    """添加新节点"""
    # 检查节点是否已存在
    for node in custom_nodes:
        if node.name == request.name:
            raise HTTPException(status_code=400, detail=f"节点 {request.name} 已存在")
    
    # 创建新节点
    new_node = NodeResponse(
        name=request.name,
        state="idle",
        cpus=request.cpus,
        mem_total=request.mem_total,
        mem_free=request.mem_total,
        gpus=request.gpus,
        gpus_free=request.gpus,
        partitions=request.partitions,
        available=True
    )
    custom_nodes.append(new_node)
    logger.info(f"添加新节点: {new_node.name}")
    return new_node


@app.delete("/api/nodes/{node_name}")
async def delete_node(node_name: str):
    """删除节点"""
    global custom_nodes
    for i, node in enumerate(custom_nodes):
        if node.name == node_name:
            custom_nodes.pop(i)
            logger.info(f"删除节点: {node_name}")
            return {"message": f"节点 {node_name} 已删除", "success": True}
    raise HTTPException(status_code=404, detail=f"节点 {node_name} 不存在")


@app.get("/api/partitions", response_model=List[PartitionResponse])
async def list_partitions():
    """获取分区列表"""
    try:
        output = run_wsl_command(["sinfo", "-o", "%P %T"])
        
        # 如果没有分区，返回演示数据
        if not output or "PARTITION" not in output:
            return get_demo_partitions()
        
        partitions = []
        lines = output.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                partitions.append(PartitionResponse(
                    name=parts[0],
                    state=parts[1],
                    nodes=1,
                    nodes_free=1,
                    total_cpus=4,
                    total_mem=8192
                ))
        
        if not partitions:
            return get_demo_partitions()
            
        return partitions
    except Exception as e:
        return get_demo_partitions()


def get_demo_partitions() -> List[PartitionResponse]:
    """返回演示分区数据"""
    return [
        PartitionResponse(
            name="default",
            state="up",
            nodes=4,
            nodes_free=3,
            total_cpus=192,
            total_mem=768000
        ),
        PartitionResponse(
            name="gpu",
            state="up",
            nodes=2,
            nodes_free=1,
            total_cpus=64,
            total_mem=256000
        ),
        PartitionResponse(
            name="cpu",
            state="up",
            nodes=2,
            nodes_free=2,
            total_cpus=128,
            total_mem=512000
        )
    ]


@app.post("/api/jobs/{job_id}/wait")
async def wait_job(job_id: str, timeout: int = 3600):
    """等待作业完成"""
    raise HTTPException(status_code=501, detail="暂不支持等待作业")


# ============ 启动 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)