"""
E-Claw 任务执行服务
包含断点续跑机制、AI模型集成、WebSocket进度推送
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Task, TaskStatus, User, Tenant


class TaskService:
    """任务服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def execute_task_async(self, task_id: str, resume_from_checkpoint: bool = False):
        """异步执行任务"""
        # 获取任务
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return
        
        # 如果是从断点恢复，恢复进度
        if resume_from_checkpoint and task.checkpoint_data:
            checkpoint = json.loads(task.checkpoint_data) if isinstance(task.checkpoint_data, str) else task.checkpoint_data
            task.progress = checkpoint.get("progress", 0)
        
        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.utcnow()
        await self.db.commit()
        
        # 推送WebSocket进度更新
        await self._notify_progress(task_id, task.progress, "running")
        
        try:
            # 根据任务类型执行不同的处理逻辑
            if task.task_type == "document_process":
                result_text = await self._execute_document_process(task)
            elif task.task_type == "data_analysis":
                result_text = await self._execute_data_analysis(task)
            elif task.task_type == "text_generation":
                result_text = await self._execute_text_generation(task)
            elif task.task_type == "qa_system":
                result_text = await self._execute_qa_system(task)
            else:
                result_text = await self._execute_general_task(task)
            
            # 计算token使用量
            input_tokens = len(task.input_text or "") // 4
            output_tokens = len(result_text) // 4
            
            # 任务完成
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.result = result_text
            task.input_tokens = input_tokens
            task.output_tokens = output_tokens
            
            # 更新配额使用
            await self._update_quota(task, input_tokens + output_tokens)
            
            # 推送完成通知
            await self._notify_completed(task_id, result_text)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            # 推送失败通知
            await self._notify_failed(task_id, str(e))
        
        task.end_time = datetime.utcnow()
        await self.db.commit()
    
    async def _execute_with_checkpoint(self, task: Task):
        """带断点保存的任务执行"""
        checkpoint_interval = 1  # 每1秒保存一次断点
        
        for progress in range(task.progress, 101, 10):
            # 检查任务是否被取消
            await self.db.refresh(task)
            if task.status == TaskStatus.CANCELLED:
                return
            
            # 更新进度
            task.progress = progress
            task.last_checkpoint_at = datetime.utcnow()
            
            # 保存断点数据
            task.checkpoint_data = json.dumps({
                "progress": progress,
                "input_text": task.input_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await self.db.commit()
            
            # 推送WebSocket进度更新
            await self._notify_progress(str(task.id), progress, "running")
            
            # 模拟处理时间
            await asyncio.sleep(checkpoint_interval)
    
    async def _execute_document_process(self, task: Task) -> str:
        """文档处理任务"""
        input_text = task.input_text or ""
        
        # 模拟文档处理
        for i in range(0, 101, 20):
            await asyncio.sleep(0.5)
            task.progress = i
            task.last_checkpoint_at = datetime.utcnow()
            task.checkpoint_data = json.dumps({
                "progress": i,
                "stage": "processing",
                "timestamp": datetime.utcnow().isoformat()
            })
            await self.db.commit()
            await self._notify_progress(str(task.id), i, "running")
        
        # 返回处理结果
        return f"文档处理完成。\n\n输入内容长度: {len(input_text)} 字符\n处理阶段: 文本提取 -> 分块 -> 向量化 -> 索引构建"
    
    async def _execute_data_analysis(self, task: Task) -> str:
        """数据分析任务"""
        input_text = task.input_text or ""
        
        # 模拟数据分析
        for i in range(0, 101, 25):
            await asyncio.sleep(0.5)
            task.progress = i
            task.last_checkpoint_at = datetime.utcnow()
            task.checkpoint_data = json.dumps({
                "progress": i,
                "stage": "analyzing",
                "timestamp": datetime.utcnow().isoformat()
            })
            await self.db.commit()
            await self._notify_progress(str(task.id), i, "running")
        
        # 返回分析结果
        return f"数据分析完成。\n\n输入内容: {input_text[:100]}...\n统计维度: 词频分析、情感分析、关键信息提取"
    
    async def _execute_text_generation(self, task: Task) -> str:
        """文本生成任务 - 集成AI模型"""
        input_text = task.input_text or ""
        
        # 模拟AI文本生成
        for i in range(0, 101, 20):
            await asyncio.sleep(0.5)
            task.progress = i
            task.last_checkpoint_at = datetime.utcnow()
            await self.db.commit()
            await self._notify_progress(str(task.id), i, "running")
        
        # 模拟AI生成结果（实际应该调用LLM API）
        generated_text = self._simulate_ai_generation(input_text)
        
        return generated_text
    
    async def _execute_qa_system(self, task: Task) -> str:
        """问答系统任务"""
        input_text = task.input_text or ""
        
        # 模拟问答处理
        for i in range(0, 101, 25):
            await asyncio.sleep(0.3)
            task.progress = i
            task.last_checkpoint_at = datetime.utcnow()
            await self.db.commit()
            await self._notify_progress(str(task.id), i, "running")
        
        # 返回问答结果
        return f"基于知识库的问答结果：\n\n问题: {input_text}\n\n回答: 这是一个基于RAG的问答系统示例。实际部署时会结合向量检索和LLM生成答案。"
    
    async def _execute_general_task(self, task: Task) -> str:
        """通用任务"""
        input_text = task.input_text or ""
        
        # 模拟通用处理
        for i in range(0, 101, 10):
            await asyncio.sleep(0.3)
            task.progress = i
            task.last_checkpoint_at = datetime.utcnow()
            task.checkpoint_data = json.dumps({
                "progress": i,
                "input_length": len(input_text),
                "timestamp": datetime.utcnow().isoformat()
            })
            await self.db.commit()
            await self._notify_progress(str(task.id), i, "running")
        
        return f"任务执行完成。\n\n输入内容: {input_text[:200]}...\n任务类型: {task.task_type}"
    
    def _simulate_ai_generation(self, input_text: str) -> str:
        """模拟AI生成（实际部署时应调用真实LLM）"""
        return f"""AI生成结果:

基于输入 "{input_text[:50]}..." 的内容，生成以下回复:

这是由AI模型生成的文本。在实际部署中，可以通过配置以下环境变量来使用不同的LLM服务:
- OPENAI_API_KEY: OpenAI API密钥
- ANTHROPIC_API_KEY: Anthropic API密钥
- 自定义LLM端点: 通过配置base_url使用其他兼容OpenAI API的服务

生成的回复将根据输入内容和任务类型进行智能处理。"""
    
    async def _update_quota(self, task: Task, tokens_used: int):
        """更新配额使用"""
        # 更新用户配额
        result = await self.db.execute(
            select(User).where(User.id == task.user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.personal_used = (user.personal_used or 0) + tokens_used
            await self.db.commit()
        
        # 更新租户配额
        if task.tenant_id:
            result = await self.db.execute(
                select(Tenant).where(Tenant.id == task.tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant.used_quota = (tenant.used_quota or 0) + tokens_used
                await self.db.commit()
    
    async def _notify_progress(self, task_id: str, progress: int, status: str):
        """推送进度更新到WebSocket"""
        try:
            from app.api.websocket import notify_task_update
            await notify_task_update(task_id, {
                "progress": progress,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass  # WebSocket推送失败不影响主流程
    
    async def _notify_completed(self, task_id: str, result: str):
        """推送任务完成通知"""
        try:
            from app.api.websocket import notify_task_completed
            await notify_task_completed(task_id, {
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
    
    async def _notify_failed(self, task_id: str, error: str):
        """推送任务失败通知"""
        try:
            from app.api.websocket import notify_task_failed
            await notify_task_failed(task_id, error)
        except Exception:
            pass
    
    async def save_checkpoint(self, task_id: str, checkpoint_data: dict):
        """手动保存断点"""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            task.checkpoint_data = json.dumps(checkpoint_data)
            task.last_checkpoint_at = datetime.utcnow()
            task.status = TaskStatus.PAUSED
            await self.db.commit()
    
    async def restore_from_checkpoint(self, task_id: str) -> dict:
        """从断点恢复"""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task and task.checkpoint_data:
            if isinstance(task.checkpoint_data, str):
                return json.loads(task.checkpoint_data)
            return task.checkpoint_data
        return {}