"""
GPU资源分配系统后端
提供GPU卡分配给应用的RESTful API
支持从K8s环境获取GPU信息
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入K8s服务
from services.k8s_gpu_service import k8s_gpu_service, K8S_MODE

app = FastAPI(title="GPU资源分配系统", version="1.1.0")

# 数据模型
class GPUCard(BaseModel):
    id: str
    name: str
    total_memory: int  # MB
    used_memory: int = 0
    status: str = "available"  # available, allocated, error
    assigned_app: Optional[str] = None
    node: Optional[str] = None  # K8s节点名称
    index: Optional[int] = None  # GPU索引

class Application(BaseModel):
    id: str
    name: str
    required_memory: int  # MB
    assigned_gpu: Optional[str] = None
    status: str = "pending"  # pending, running, stopped
    created_at: str

class AllocateRequest(BaseModel):
    app_id: str
    gpu_id: str

class ReleaseRequest(BaseModel):
    gpu_id: str

# 初始化GPU列表（从K8s或模拟数据）
def init_gpus():
    """初始化GPU列表"""
    k8s_gpus = k8s_gpu_service.get_gpu_nodes()
    logger.info(f"初始化GPU数量: {len(k8s_gpus)}")
    return [GPUCard(**gpu) for gpu in k8s_gpus]

GPUS = init_gpus()

# 应用存储
APPLICATIONS = {}

# API端点
@app.get("/")
async def root():
    return {
        "message": "GPU资源分配系统API", 
        "version": "1.1.0",
        "k8s_mode": K8S_MODE
    }

@app.get("/api/gpus", response_model=List[GPUCard])
async def get_gpus():
    """获取所有GPU卡状态"""
    # 刷新GPU状态
    gpu_dicts = [gpu.dict() for gpu in GPUS]
    refreshed = k8s_gpu_service.refresh_gpu_status(gpu_dicts)
    return [GPUCard(**g) for g in refreshed]

@app.get("/api/gpus/{gpu_id}", response_model=GPUCard)
async def get_gpu(gpu_id: str):
    """获取指定GPU卡状态"""
    for gpu in GPUS:
        if gpu.id == gpu_id:
            return gpu
    raise HTTPException(status_code=404, detail="GPU卡不存在")

@app.get("/api/k8s/pods", response_model=List[dict])
async def get_gpu_pods():
    """获取使用GPU的K8s Pod列表"""
    return k8s_gpu_service.get_pods_with_gpu()

@app.get("/api/k8s/status")
async def get_k8s_status():
    """获取K8s连接状态"""
    return {
        "mode": K8S_MODE,
        "client_initialized": k8s_gpu_service.k8s_client is not None
    }

@app.get("/api/applications", response_model=List[Application])
async def get_applications():
    """获取所有应用"""
    return list(APPLICATIONS.values())

@app.post("/api/applications")
async def create_application(app: Application):
    """创建新应用"""
    app.id = str(uuid.uuid4())[:8]
    app.created_at = datetime.now().isoformat()
    APPLICATIONS[app.id] = app
    return app

@app.post("/api/allocate")
async def allocate_gpu(request: AllocateRequest):
    """分配GPU给应用"""
    # 查找GPU
    gpu = None
    for g in GPUS:
        if g.id == request.gpu_id:
            gpu = g
            break
    
    if not gpu:
        raise HTTPException(status_code=404, detail="GPU卡不存在")
    
    if gpu.status != "available":
        raise HTTPException(status_code=400, detail="GPU卡不可用")
    
    # 查找应用
    app = APPLICATIONS.get(request.app_id)
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    if app.required_memory > gpu.total_memory:
        raise HTTPException(status_code=400, detail="应用所需内存超过GPU总内存")
    
    # 分配GPU
    gpu.status = "allocated"
    gpu.assigned_app = app.id
    gpu.used_memory = app.required_memory
    
    app.assigned_gpu = gpu.id
    app.status = "running"
    
    return {"message": "GPU分配成功", "gpu": gpu, "app": app}

@app.post("/api/release")
async def release_gpu(request: ReleaseRequest):
    """释放GPU"""
    gpu = None
    for g in GPUS:
        if g.id == request.gpu_id:
            gpu = g
            break
    
    if not gpu:
        raise HTTPException(status_code=404, detail="GPU卡不存在")
    
    if gpu.status == "available":
        raise HTTPException(status_code=400, detail="GPU卡已经是空闲状态")
    
    # 释放GPU
    app_id = gpu.assigned_app
    gpu.status = "available"
    gpu.assigned_app = None
    gpu.used_memory = 0
    
    # 更新应用状态
    if app_id and app_id in APPLICATIONS:
        APPLICATIONS[app_id].assigned_gpu = None
        APPLICATIONS[app_id].status = "stopped"
    
    return {"message": "GPU释放成功", "gpu": gpu}

@app.delete("/api/applications/{app_id}")
async def delete_application(app_id: str):
    """删除应用"""
    if app_id not in APPLICATIONS:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    app = APPLICATIONS[app_id]
    
    # 如果应用占用了GPU，释放GPU
    if app.assigned_gpu:
        for gpu in GPUS:
            if gpu.id == app.assigned_gpu:
                gpu.status = "available"
                gpu.assigned_app = None
                gpu.used_memory = 0
                break
    
    del APPLICATIONS[app_id]
    return {"message": "应用删除成功"}

@app.post("/api/gpus/refresh")
async def refresh_gpus():
    """手动刷新GPU列表（从K8s重新获取）"""
    global GPUS
    k8s_gpus = k8s_gpu_service.get_gpu_nodes()
    GPUS = [GPUCard(**gpu) for gpu in k8s_gpus]
    return {"message": "GPU列表已刷新", "count": len(GPUS)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)