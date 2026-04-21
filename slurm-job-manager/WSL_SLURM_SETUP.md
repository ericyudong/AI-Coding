# WSL2 Ubuntu 中 Slurm 安装指南

本文档提供在 WSL2 Ubuntu 中手动安装 Slurm 的分步说明。

## 步骤 1: 打开 WSL2 Ubuntu

在 PowerShell 或命令提示符中运行:
```powershell
wsl -d Ubuntu
```

## 步骤 2: 更新系统

```bash
sudo apt update && sudo apt upgrade -y
```

## 步骤 3: 安装 Slurm

使用 apt 安装（推荐）:

```bash
sudo apt install -y slurm-wlm slurmctld slurmd munge
```

## 步骤 4: 配置目录权限

```bash
sudo mkdir -p /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm
sudo chmod 755 /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm
sudo chown -R slurm:slurm /var/spool/slurm /var/log/slurm 2>/dev/null || true
```

## 步骤 5: 创建 Slurm 配置文件

```bash
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
SwitchType=switch/none
MpiDefault=none
SlurmctldPidFile=/var/run/slurmctld.pid
SlurmdPidFile=/var/run/slurmd.pid
ProctrackType=proctrack/cgroup
ReturnToService=2

NodeName=localhost State=UNKNOWN
PartitionName=default Nodes=ALL Default=YES MaxTime=INFINITE State=UP
EOF
```

创建 cgroup 配置:
```bash
sudo tee /etc/slurm/cgroup.conf > /dev/null << 'EOF'
CgroupAutomount=yes
ConstrainCores=no
ConstrainRAMSpace=yes
EOF
```

## 步骤 6: 启动 Munge 服务

```bash
sudo service munge start
```

验证 munge 状态:
```bash
sudo service munge status
```

## 步骤 7: 启动 Slurm 控制器

```bash
sudo slurmctld -c
```

验证是否启动成功:
```bash
sinfo
```

如果看到节点信息，说明安装成功!

## 测试 Slurm

### 查看节点状态
```bash
sinfo
```

### 提交测试作业
创建一个测试脚本:
```bash
cat > test_job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=test_job
#SBATCH --output=test_output_%j.txt
echo "Hello from Slurm!"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_JOB_NODELIST"
sleep 5
echo "Job completed!"
EOF
```

提交作业:
```bash
sbatch test_job.sh
```

### 查看作业状态
```bash
squeue
```

### 查看作业输出
```bash
cat test_output_<job_id>.txt
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `sinfo` | 查看节点状态 |
| `squeue` | 查看作业队列 |
| `sbatch <script>` | 提交作业 |
| `scancel <job_id>` | 取消作业 |
| `scontrol show job <id>` | 查看作业详情 |
| `scontrol show nodes` | 查看节点详情 |
| `scontrol show partitions` | 查看分区详情 |
| `sacct` | 查看历史作业 |

## 故障排除

### Munge 密钥问题
如果遇到 munge 认证错误:
```bash
sudo /usr/sbin/create-munge-key -f
sudo service munge restart
```

### 查看日志
```bash
sudo tail -f /var/log/slurm/slurmctld.log
```

### 重启服务
```bash
sudo scancel -u all
sudo killall slurmctld
sudo slurmctld -c
```

## 连接到 Windows 端

从 Windows 连接到 WSL2 中的 Slurm:
- 使用 `wsl -d Ubuntu` 登录 WSL2
- WSL2 的 IP 地址可在 Windows 中通过 `wsl hostname -I` 获取

或者修改后端代码指向 WSL2 的 IP 地址。