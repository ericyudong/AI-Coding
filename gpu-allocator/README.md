# GPU资源分配系统

一个用于将NVIDIA GPU按卡分配给应用的Web管理系统。

## 系统架构

- **后端**: FastAPI (Python)
- **前端**: 纯HTML/CSS/JavaScript (无需构建)

## 快速开始

### 1. 安装依赖

```bash
cd gpu-allocator
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd backend
python main.py
```

后端服务将在 http://localhost:8000 启动

### 3. 打开前端页面

在浏览器中打开 `frontend/index.html`

## API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/gpus | 获取所有GPU卡状态 |
| GET | /api/gpus/{gpu_id} | 获取指定GPU卡状态 |
| GET | /api/applications | 获取所有应用 |
| POST | /api/applications | 创建新应用 |
| POST | /api/allocate | 分配GPU给应用 |
| POST | /api/release | 释放GPU |
| DELETE | /api/applications/{app_id} | 删除应用 |

## 功能特性

1. **GPU资源池**: 展示所有GPU卡的状态（空闲/已分配）
2. **应用管理**: 创建、删除应用，查看应用状态
3. **按卡分配**: 将GPU按卡分配给应用
4. **实时刷新**: 每5秒自动刷新状态
5. **内存使用可视化**: 显示GPU内存使用进度条

## 模拟数据

系统预置了8张GPU卡:
- 4x NVIDIA A100-40GB (每张 40960MB)
- 4x NVIDIA RTX 4090 (每张 24576MB)