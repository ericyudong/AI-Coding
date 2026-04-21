# Slurm作业管理系统

基于Slurm的分布式HPC作业管理与监控Web前端系统。

## 功能特性

- **作业管理**: 提交、查看、取消Slurm作业
- **实时监控**: 作业状态自动刷新 (每10秒)
- **节点状态**: 查看集群节点资源使用情况
- **统计分析**: 作业状态统计看板
- **美观UI**: 现代深色主题设计

## 项目结构

```
slurm-job-manager/
├── backend/
│   ├── main.py          # FastAPI后端服务
│   └── requirements.txt # Python依赖
├── frontend/
│   └── index.html       # Web前端页面
├── run.bat              # Windows启动脚本
├── install_slurm.sh     # Slurm完整安装脚本
├── install_slurm_simple.sh  # Slurm简易安装脚本
├── WSL_SLURM_SETUP.md   # WSL2安装指南
└── README.md            # 本文件
```

## 快速开始

### 第一步：安装Slurm环境

#### 方式A: WSL2 Ubuntu (推荐)

1. 打开PowerShell，运行:
```powershell
wsl -d Ubuntu
```

2. 在WSL2中执行安装:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y slurm-wlm slurmctld slurmd munge

# 配置目录
sudo mkdir -p /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm
sudo chmod 755 /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm

# 创建配置文件
sudo tee /etc/slurm/slurm.conf > /dev/null << 'EOF'
ClusterName=localcluster
ControlMachine=localhost
ControlAddr=127.0.0.1
SlurmUser=slurm
SlurmctldPort=6817
SlurmdPort=6818
AuthType=auth/munge
StateSaveLocation=/var/spool/slurm/ctld
SlurmdSpoolDir=/var/spool/slurm/d
NodeName=localhost State=UNKNOWN
PartitionName=default Nodes=ALL Default=YES MaxTime=INFINITE State=UP
EOF

# 启动服务
sudo service munge start
sudo slurmctld -c
sinfo
```

详细步骤请参考 [WSL_SLURM_SETUP.md](./WSL_SLURM_SETUP.md)

#### 方式B: 模拟模式 (不需要真实Slurm)

后端已内置模拟模式，如果没有Slurm环境会自动使用模拟数据。

### 第二步：启动后端

```bash
cd slurm-job-manager
pip install -r backend\requirements.txt
python backend\main.py
```

### 第三步：打开前端

在浏览器中打开 `frontend\index.html`

### 访问地址

- 后端API: http://localhost:8002
- API文档: http://localhost:8002/docs

## API端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/jobs | 获取所有作业 |
| GET | /api/jobs/{job_id} | 获取作业详情 |
| POST | /api/jobs | 提交新作业 |
| DELETE | /api/jobs/{job_id} | 取消作业 |
| GET | /api/statistics | 获取作业统计 |
| GET | /api/nodes | 获取节点列表 |
| GET | /api/partitions | 获取分区列表 |

## 作业状态

- **PENDING**: 等待中
- **RUNNING**: 运行中
- **COMPLETED**: 已完成
- **FAILED**: 失败
- **CANCELLED**: 已取消
- **TIMEOUT**: 超时
- **UNKNOWN**: 未知

## 依赖

- Python 3.8+
- FastAPI
- Uvicorn
- Pydantic

## 注意事项

- 如果Slurm命令(sbatch/squeue/scontrol)不可用，系统将自动使用模拟模式
- 前端页面需要与后端API通信，请确保两者均可访问
- 作业列表每10秒自动刷新一次
