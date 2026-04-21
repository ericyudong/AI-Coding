"""
E-Claw WebSocket接口
支持实时任务状态推送、日志流等
"""
import json
import asyncio
from typing import Dict, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.database import AsyncSessionLocal
from app.models import User


# 连接管理
class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 活跃连接: user_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 任务订阅: task_id -> set of websockets
        self.task_subscriptions: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """连接"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """断开连接"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # 移除所有任务订阅
        for task_id in list(self.task_subscriptions.keys()):
            self.task_subscriptions[task_id].discard(websocket)
            if not self.task_subscriptions[task_id]:
                del self.task_subscriptions[task_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        """发送个人消息"""
        if user_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.add(websocket)
            
            # 清理断开的连接
            for ws in disconnected:
                self.active_connections[user_id].discard(ws)
    
    async def broadcast(self, message: dict):
        """广播消息"""
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass
    
    def subscribe_task(self, websocket: WebSocket, task_id: str):
        """订阅任务"""
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        self.task_subscriptions[task_id].add(websocket)
    
    def unsubscribe_task(self, websocket: WebSocket, task_id: str):
        """取消订阅任务"""
        if task_id in self.task_subscriptions:
            self.task_subscriptions[task_id].discard(websocket)
    
    async def send_task_update(self, message: dict, task_id: str):
        """发送任务更新"""
        if task_id in self.task_subscriptions:
            disconnected = set()
            for websocket in self.task_subscriptions[task_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.add(websocket)
            
            # 清理断开的连接
            for ws in disconnected:
                self.task_subscriptions[task_id].discard(ws)


# 全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点
    
    客户端连接时需要提供token参数:
    ws://host/ws?token=xxx
    
    支持的消息类型:
    - subscribe_task: 订阅任务进度
    - unsubscribe_task: 取消订阅任务
    - ping: 心跳
    """
    user = None
    user_id = None
    
    try:
        # 获取token
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001, reason="Missing token")
            return
        
        # 验证用户
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # 连接
        await manager.connect(websocket, user_id)
        
        # 发送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 处理消息
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_message(websocket, message, user_id)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
    
    except WebSocketDisconnect:
        pass
    finally:
        if user_id:
            manager.disconnect(websocket, user_id)


async def handle_message(websocket: WebSocket, message: dict, user_id: str):
    """处理WebSocket消息"""
    msg_type = message.get("type")
    
    if msg_type == "subscribe_task":
        # 订阅任务
        task_id = message.get("task_id")
        if task_id:
            manager.subscribe_task(websocket, task_id)
            await websocket.send_json({
                "type": "subscribed",
                "task_id": task_id
            })
    
    elif msg_type == "unsubscribe_task":
        # 取消订阅任务
        task_id = message.get("task_id")
        if task_id:
            manager.unsubscribe_task(websocket, task_id)
            await websocket.send_json({
                "type": "unsubscribed",
                "task_id": task_id
            })
    
    elif msg_type == "ping":
        # 心跳
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })


# ============== 任务状态推送 ==============

async def notify_task_update(task_id: str, update: dict):
    """通知任务更新"""
    message = {
        "type": "task_update",
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": update
    }
    await manager.send_task_update(message, task_id)


async def notify_task_completed(task_id: str, result: dict):
    """通知任务完成"""
    message = {
        "type": "task_completed",
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "result": result
    }
    await manager.send_task_update(message, task_id)


async def notify_task_failed(task_id: str, error: str):
    """通知任务失败"""
    message = {
        "type": "task_failed",
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "error": error
    }
    await manager.send_task_update(message, task_id)


# ============== 系统通知 ==============

async def notify_system_broadcast(message: dict):
    """系统广播"""
    await manager.broadcast({
        "type": "system",
        "timestamp": datetime.utcnow().isoformat(),
        "message": message
    })


async def notify_user_message(user_id: str, message: dict):
    """发送用户消息"""
    await manager.send_personal_message({
        "type": "message",
        "timestamp": datetime.utcnow().isoformat(),
        "message": message
    }, user_id)