"""
E-Claw 日志查询接口
系统日志、审计日志查询
"""
import os
import json
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.models import User, UserRole

router = APIRouter()

# 日志文件路径
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "e-claw.log")


# ============== 日志数据模型 ==============

class LogEntry(BaseModel):
    """日志条目"""
    id: str
    timestamp: str
    level: str
    source: str
    message: str
    module: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    traceback: Optional[str] = None


class LogQuery(BaseModel):
    """日志查询请求"""
    level: Optional[str] = None
    source: Optional[str] = None
    keyword: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 100


class LogStats(BaseModel):
    """日志统计"""
    total: int
    error: int
    warning: int
    info: int
    debug: int


# ============== 日志存储 ==============

class LogStore:
    """日志存储器"""
    
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self._initialize_demo_logs()
    
    def _initialize_demo_logs(self):
        """初始化演示日志"""
        import random
        import uuid
        
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        sources = ['system', 'auth', 'task', 'knowledge', 'api']
        
        messages = {
            'DEBUG': [
                'Starting request processing',
                'Database query executed in 5ms',
                'Cache hit for key: user_session_123',
                'Loading configuration from file',
                'WebSocket connection established',
                'Processing batch task: 100 items',
                'Memory usage: 256MB'
            ],
            'INFO': [
                'User login successful',
                'Task created successfully',
                'Document uploaded to knowledge base',
                'System health check passed',
                'Backup completed successfully',
                'User logout: user_id=12345',
                'API request: GET /api/v1/tasks'
            ],
            'WARNING': [
                'High memory usage detected: 85%',
                'Rate limit approaching for API key',
                'Token quota low for user 12345',
                'Disk space below threshold: 20%',
                'Session timeout for user',
                'Deprecated API endpoint called: /api/v1/old'
            ],
            'ERROR': [
                'Database connection failed: timeout',
                'Failed to process task: invalid input',
                'Authentication failed: invalid token',
                'API request failed: 500 internal error',
                'File upload failed: size exceeds limit',
                'Task execution timeout after 300s'
            ],
            'CRITICAL': [
                'Database connection lost',
                'System out of memory',
                'Disk write failed: no space left',
                'Security breach detected: multiple failed login attempts',
                'Primary node unavailable'
            ]
        }
        
        now = datetime.now()
        
        for i in range(500):
            level = levels[random.randint(0, len(levels) - 1)]
            source = sources[random.randint(0, len(sources) - 1)]
            level_messages = messages[level]
            message = level_messages[random.randint(0, len(level_messages) - 1)]
            
            timestamp = now - timedelta(
                minutes=random.randint(0, 1440),  # Last 24 hours
                seconds=random.randint(0, 59)
            )
            
            log_entry = {
                'id': str(uuid.uuid4()),
                'timestamp': timestamp.isoformat(),
                'level': level,
                'source': source,
                'message': message,
                'module': f'app.api.v1.{source}',
                'request_id': f'req-{uuid.uuid4().hex[:12]}',
                'user_id': f'user-{random.randint(1, 100)}' if random.random() > 0.3 else None,
                'traceback': self._generate_traceback(level, source) if level in ['ERROR', 'CRITICAL'] else None
            }
            
            self.logs.append(log_entry)
        
        # 按时间排序
        self.logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    def _generate_traceback(self, level: str, source: str) -> str:
        """生成堆栈跟踪"""
        lines = [
            f'Traceback (most recent call last):',
            f'  File "/app/api/v1/{source}.py", line {random.randint(10, 100)}, in process',
            f'    raise ValueError("Error occurred")',
            f'ValueError: Some error message'
        ]
        return '\n'.join(lines)
    
    def query(self, 
              level: Optional[str] = None,
              source: Optional[str] = None,
              keyword: Optional[str] = None,
              start_date: Optional[str] = None,
              end_date: Optional[str] = None,
              page: int = 1,
              page_size: int = 100) -> Dict[str, Any]:
        """查询日志"""
        import random
        
        # 筛选日志
        filtered_logs = self.logs.copy()
        
        if level:
            filtered_logs = [log for log in filtered_logs if log['level'] == level]
        
        if source:
            filtered_logs = [log for log in filtered_logs if log['source'] == source]
        
        if keyword:
            keyword_lower = keyword.lower()
            filtered_logs = [log for log in filtered_logs if keyword_lower in log['message'].lower()]
        
        if start_date:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] >= start_date]
        
        if end_date:
            filtered_logs = [log for log in filtered_logs if log['timestamp'] <= end_date]
        
        # 计算统计数据
        total = len(filtered_logs)
        error = len([l for l in filtered_logs if l['level'] in ['ERROR', 'CRITICAL']])
        warning = len([l for l in filtered_logs if l['level'] == 'WARNING'])
        info = len([l for l in filtered_logs if l['level'] == 'INFO'])
        debug = len([l for l in filtered_logs if l['level'] == 'DEBUG'])
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        paginated_logs = filtered_logs[start:end]
        
        return {
            'logs': paginated_logs,
            'total': total,
            'stats': {
                'total': total,
                'error': error,
                'warning': warning,
                'info': info,
                'debug': debug
            },
            'page': page,
            'page_size': page_size
        }


# 全局日志存储实例
log_store = LogStore()


# ============== 日志查询接口 ==============

@router.get("/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    source: Optional[str] = Query(None, description="日志来源: system, auth, task, knowledge, api"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    start_date: Optional[str] = Query(None, description="开始日期 ISO格式"),
    end_date: Optional[str] = Query(None, description="结束日期 ISO格式"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """查询日志列表"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    return log_store.query(
        level=level,
        source=source,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size
    )


@router.get("/logs/{log_id}")
async def get_log_detail(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取日志详情"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    for log in log_store.logs:
        if log['id'] == log_id:
            return log
    
    raise HTTPException(status_code=404, detail="Log not found")


@router.get("/logs/stats/summary")
async def get_log_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取日志统计摘要"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    result = log_store.query(page=1, page_size=1)
    return result['stats']


@router.delete("/logs")
async def clear_logs(
    confirm: bool = Query(False, description="确认清空日志"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """清空日志"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Please set confirm=true to clear logs"
        )
    
    # 清空日志
    log_store.logs = []
    
    return {"message": "Logs cleared successfully"}


@router.post("/logs/export")
async def export_logs(
    level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    format: str = Query("text", description="导出格式: text, json"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """导出日志"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    result = log_store.query(
        level=level,
        source=source,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        page=1,
        page_size=10000  # Max export
    )
    
    logs = result['logs']
    
    if format == "json":
        return {
            "format": "json",
            "count": len(logs),
            "logs": logs
        }
    
    # Plain text format
    content = '\n'.join([
        f'[{log["timestamp"]}] [{log["level"]}] [{log["source"]}] {log["message"]}'
        for log in logs
    ])
    
    return {
        "format": "text",
        "count": len(logs),
        "content": content
    }