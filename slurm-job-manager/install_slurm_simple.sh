#!/bin/bash
# Slurm 简易安装脚本 - 通过apt安装

echo "========================================="
echo "Slurm 简易安装脚本 (apt方式)"
echo "========================================="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root用户运行: sudo bash install_slurm_simple.sh"
    exit 1
fi

echo "[1/5] 更新系统包..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

echo "[2/5] 安装Slurm (通过apt)..."
apt-get install -y -qq slurm-wlm slurmctld slurmd munge 2>/dev/null

if [ $? -ne 0 ]; then
    echo "apt安装失败，尝试安装依赖后重试..."
    apt-get install -y -qq munge
    apt-get install -y -qq slurm-wlm 2>/dev/null || true
fi

echo "[3/5] 配置Slurm目录..."
mkdir -p /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm
chown slurm:slurm /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm 2>/dev/null || true
chmod 755 /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm

echo "[4/5] 创建基本配置文件..."

# 创建slurm.conf
cat > /etc/slurm/slurm.conf << 'EOF'
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

# 创建cgroup.conf
cat > /etc/slurm/cgroup.conf << 'EOF'
CgroupAutomount=yes
ConstrainCores=no
ConstrainRAMSpace=yes
EOF

chmod 644 /etc/slurm/slurm.conf /etc/slurm/cgroup.conf

echo "[5/5] 启动服务..."
# 启动munge
service munge start 2>/dev/null || true

# 启动slurmctld
slurmctld -D -c 2>/dev/null &

sleep 2

echo ""
echo "========================================="
echo "安装完成!"
echo "========================================="
echo ""
echo "验证安装:"
echo "  sinfo          # 查看节点状态"
echo "  squeue         # 查看作业队列"
echo ""
echo "常用命令:"
echo "  sbatch <script>   # 提交作业"
echo "  scancel <job_id>  # 取消作业"
echo "  scontrol show job # 查看作业详情"