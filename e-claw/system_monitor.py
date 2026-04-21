"""系统资源监控工具"""

import psutil
import time
from datetime import datetime


def get_cpu_usage():
    """获取CPU使用率"""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    per_cpu = psutil.cpu_percent(interval=1, percpu=True)
    return {
        "总使用率": f"{cpu_percent}%",
        "CPU核心数": cpu_count,
        "各核心使用率": [f"{p}%" for p in per_cpu]
    }


def get_memory_usage():
    """获取内存使用情况"""
    mem = psutil.virtual_memory()
    return {
        "总内存": f"{mem.total / (1024**3):.2f} GB",
        "已使用": f"{mem.used / (1024**3):.2f} GB",
        "可用": f"{mem.available / (1024**3):.2f} GB",
        "使用率": f"{mem.percent}%"
    }


def get_disk_usage():
    """获取硬盘使用情况"""
    partitions = psutil.disk_partitions()
    disk_info = []
    for partition in partitions:
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info.append({
                "盘符": partition.device,
                "挂载点": partition.mountpoint,
                "文件系统": partition.fstype,
                "总容量": f"{usage.total / (1024**3):.2f} GB",
                "已使用": f"{usage.used / (1024**3):.2f} GB",
                "可用": f"{usage.free / (1024**3):.2f} GB",
                "使用率": f"{usage.percent}%"
            })
        except PermissionError:
            continue
    return disk_info


def get_network_usage():
    """获取网络使用情况"""
    net_io = psutil.net_io_counters()
    return {
        "发送": f"{net_io.bytes_sent / (1024**2):.2f} MB",
        "接收": f"{net_io.bytes_recv / (1024**2):.2f} MB",
        "发送包": net_io.packets_sent,
        "接收包": net_io.packets_recv
    }


def get_disk_io():
    """获取磁盘IO情况"""
    disk_io = psutil.disk_io_counters()
    return {
        "读取字节": f"{disk_io.read_bytes / (1024**2):.2f} MB",
        "写入字节": f"{disk_io.write_bytes / (1024**2):.2f} MB",
        "读取次数": disk_io.read_count,
        "写入次数": disk_io.write_count
    }


def get_system_info():
    """获取系统基本信息"""
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    return {
        "系统启动时间": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
        "运行时间": str(datetime.now() - boot_time).split(".")[0]
    }


def print_section(title, data):
    """打印分组信息"""
    print(f"\n{'='*40}")
    print(f"  {title}")
    print('='*40)
    if isinstance(data, list):
        for item in data:
            for key, value in item.items():
                print(f"  {key}: {value}")
            print()
    else:
        for key, value in data.items():
            print(f"  {key}: {value}")


def monitor(interval=1, duration=None):
    """持续监控资源使用情况
    
    Args:
        interval: 刷新间隔（秒）
        duration: 监控时长（秒），None表示无限
    """
    print("系统资源监控")
    print(f"刷新间隔: {interval}秒")
    if duration:
        print(f"监控时长: {duration}秒")
    print("按 Ctrl+C 退出\n")
    
    start_time = time.time()
    
    while True:
        print(f"\n{'#'*50}")
        print(f"  采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('#'*50)
        
        print_section("CPU 使用情况", get_cpu_usage())
        print_section("内存使用情况", get_memory_usage())
        print_section("硬盘使用情况", get_disk_usage())
        print_section("网络使用情况", get_network_usage())
        print_section("磁盘IO情况", get_disk_io())
        print_section("系统信息", get_system_info())
        
        if duration and (time.time() - start_time) >= duration:
            break
        
        time.sleep(interval)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--once":
            print_section("CPU 使用情况", get_cpu_usage())
            print_section("内存使用情况", get_memory_usage())
            print_section("硬盘使用情况", get_disk_usage())
            print_section("网络使用情况", get_network_usage())
            print_section("磁盘IO情况", get_disk_io())
            print_section("系统信息", get_system_info())
        elif sys.argv[1] == "--monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 2
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else None
            monitor(interval, duration)
        else:
            print("用法:")
            print("  python system_monitor.py --once      # 单次采集")
            print("  python system_monitor.py --monitor    # 持续监控")
            print("  python system_monitor.py --monitor 2 # 每2秒刷新")
            print("  python system_monitor.py --monitor 2 60 # 监控60秒")
    else:
        monitor(interval=2)