#!/bin/bash
# Slurm单节点安装脚本 (适用于Ubuntu WSL2)

echo "========================================="
echo "Slurm 单节点安装脚本"
echo "========================================="

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root用户运行: sudo bash install_slurm.sh"
    exit 1
fi

echo "[1/8] 更新系统..."
apt-get update
apt-get upgrade -y

echo "[2/8] 安装依赖..."
apt-get install -y \
    build-essential \
    wget \
    libssl-dev \
    libreadline-dev \
    libncurses5-dev \
    libpam0g-dev \
    munge \
    mariadb-server \
    libmariadb-dev \
    libmariadb-dev-compat \
    python3 \
    rpm

echo "[3/8] 创建slurm用户..."
id -u slurm &>/dev/null || useradd -r -M slurm

echo "[4/8] 配置Munge密钥..."
chmod 755 /var/log
chmod 755 /var/lib
chmod 755 /etc
mkdir -p /var/lib/munge /var/log/munge /etc/munge
dd if=/dev/urandom bs=1 count=1024 2>/dev/null | dd of=/etc/munge/munge.key 2>/dev/null
chown munge:munge /etc/munge/munge.key
chmod 400 /etc/munge/munge.key

echo "[5/8] 启动Munge服务..."
systemctl enable munge
systemctl start munge
systemctl status munge --no-pager

echo "[6/8] 安装Slurm..."
cd /tmp
SLURM_VERSION="23.11.4"
wget -q https://download.schedmd.com/slurm/slurm-${SLURM_VERSION}.tar.bz2
if [ ! -f slurm-${SLURM_VERSION}.tar.bz2 ]; then
    echo "下载失败，尝试使用apt安装..."
    apt-get install -y slurm-wlm slurmctld slurmd
    echo "Slurm安装完成 (apt方式)"
    exit 0
fi

tar xjf slurm-${SLURM_VERSION}.tar.bz2
cd slurm-${SLURM_VERSION}
./configure --prefix=/usr/local --sysconfdir=/etc/slurm
make -j$(nproc)
make install

echo "[7/8] 配置Slurm..."
mkdir -p /etc/slurm /var/log/slurm /var/spool/slurm/ctld /var/spool/slurm/d
chown -R slurm:slurm /var/log/slurm /var/spool/slurm
chmod -R 755 /var/log/slurm /var/spool/slurm

# 创建slurm.conf配置文件
cat > /etc/slurm/slurm.conf << 'EOF'
# Slurm配置 - 单节点
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

# 节点配置
NodeName=localhost State=UNKNOWN

# 分区配置
PartitionName=default Nodes=ALL Default=YES MaxTime=INFINITE State=UP
EOF

# 创建cgroup.conf
cat > /etc/slurm/cgroup.conf << 'EOF'
CgroupAutomount=yes
ConstrainCores=no
ConstrainRAMSpace=yes
EOF

# 创建gres.conf (如果有GPU)
cat > /etc/slurm/gres.conf << 'EOF'
# GPU配置示例
# NodeName=localhost Name=gpu File=/dev/nvidia0
EOF

# 复制相关文件
cp /etc/slurm/slurm.conf /etc/slurm/slurmdbd.conf 2>/dev/null || true

echo "[8/8] 启动Slurm服务..."
chown -R slurm:slurm /etc/slurm

# 启动slurmctld
slurmctld -c

echo ""
echo "========================================="
echo "Slurm安装完成!"
echo "========================================="
echo ""
echo "常用命令:"
echo "  查看节点: sinfo"
echo "  查看作业: squeue"
echo "  提交作业: sbatch <script>"
echo "  取消作业: scancel <job_id>"
echo "  查看分区: scontrol show partition"
echo ""
echo "服务状态:"
systemctl status munge --no-pager
sinfo 2>/dev/null || echo "sinfo命令可用"