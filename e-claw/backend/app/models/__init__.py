"""
E-Claw 数据模型
"""
import uuid as uuid_module
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any, TYPE_CHECKING
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise uses
    CHAR(36) for storage (for SQLite).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid_module.UUID):
                return str(value)
            else:
                return str(uuid_module.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return uuid_module.UUID(value)


from sqlalchemy.dialects.postgresql import UUID


class UserRole(str, Enum):
    """用户角色"""
    EMPLOYEE = "employee"          # 员工
    DEPT_ADMIN = "dept_admin"      # 部门管理员
    SUPER_ADMIN = "super_admin"    # 超级管理员
    OPS = "ops"                    # 运维


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"           # 排队中
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
    PAUSED = "paused"             # 已暂停（断点续跑）


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Tenant(Base):
    """租户（部门）"""
    __tablename__ = "tenants"
    
    id = Column(GUID(), primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    status = Column(String(20), default="active")  # active, disabled
    
    # 资源配额
    total_quota = Column(Integer, default=1000000)  # Token配额
    used_quota = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    users = relationship("User", back_populates="tenant")
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant")
    tasks = relationship("Task", back_populates="tenant")


class User(Base):
    """用户"""
    __tablename__ = "users"
    
    id = Column(GUID(), primary_key=True)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"))
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE)
    status = Column(String(20), default="active")  # active, disabled, locked
    
    # 个人配额
    personal_quota = Column(Integer, default=100000)
    personal_used = Column(Integer, default=0)
    
    # 认证
    last_login = Column(DateTime)
    login_failed_count = Column(Integer, default=0)
    locked_until = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    tenant = relationship("Tenant", back_populates="users")
    tasks = relationship("Task", back_populates="user")
    personal_knowledge = relationship("KnowledgeBase", back_populates="owner")


class Task(Base):
    """AI任务"""
    __tablename__ = "tasks"
    
    id = Column(GUID(), primary_key=True)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"))
    user_id = Column(GUID(), ForeignKey("users.id"))
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.MEDIUM)
    
    # 任务内容
    task_type = Column(String(50))  # document_process, data_analysis, etc.
    input_text = Column(Text)
    input_files = Column(JSON)  # 文件列表
    
    # 执行结果
    result = Column(Text)
    result_files = Column(JSON)
    error_message = Column(Text)
    
    # 进度
    progress = Column(Integer, default=0)
    
    # 断点续跑
    checkpoint_data = Column(JSON)
    last_checkpoint_at = Column(DateTime)
    
    # Token消耗
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    
    # Docker环境
    docker_container_id = Column(String(100))  # Docker容器ID
    docker_container_name = Column(String(100))  # 容器名称
    docker_status = Column(String(20))  # running, stopped, removed
    docker_url = Column(String(500))  # 访问URL
    docker_port = Column(Integer)  # 端口号
    docker_created_at = Column(DateTime)  # Docker创建时间
    docker_image_template = Column(String(50))  # 镜像模板ID: openclaw, linux
    
    # 时间
    submit_time = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    
    # 关系
    tenant = relationship("Tenant", back_populates="tasks")
    user = relationship("User", back_populates="tasks")


class KnowledgeBase(Base):
    """知识库"""
    __tablename__ = "knowledge_bases"
    
    id = Column(GUID(), primary_key=True)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"))
    owner_id = Column(GUID(), ForeignKey("users.id"))
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    type = Column(String(20))  # personal, dept_shared
    
    # 状态
    status = Column(String(20), default="active")  # active, archived
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    
    # 统计
    doc_count = Column(Integer, default=0)
    total_size = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    tenant = relationship("Tenant", back_populates="knowledge_bases")
    owner = relationship("User", back_populates="personal_knowledge")
    documents = relationship("Document", back_populates="knowledge_base")


class Document(Base):
    """知识库文档"""
    __tablename__ = "documents"
    
    id = Column(GUID(), primary_key=True)
    knowledge_base_id = Column(GUID(), ForeignKey("knowledge_bases.id"))
    
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    file_type = Column(String(50))
    file_size = Column(Integer)
    
    # 向量索引
    vector_ids = Column(JSON)
    chunk_count = Column(Integer, default=0)
    
    status = Column(String(20), default="pending")  # pending, indexed, failed
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"
    
    id = Column(GUID(), primary_key=True)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"))
    user_id = Column(GUID(), ForeignKey("users.id"))
    
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))  # user, task, knowledge, etc.
    resource_id = Column(String(100))
    
    # 请求信息
    method = Column(String(10))
    path = Column(String(500))
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    # 请求/响应
    request_body = Column(JSON)
    response_status = Column(Integer)
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 租户隔离索引
    __table_args__ = (
        Index('idx_audit_tenant_created', 'tenant_id', 'created_at'),
    )


class TokenUsage(Base):
    """Token使用记录"""
    __tablename__ = "token_usage"
    
    id = Column(GUID(), primary_key=True)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"))
    user_id = Column(GUID(), ForeignKey("users.id"))
    task_id = Column(GUID(), ForeignKey("tasks.id"))
    
    # 使用量
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 模型信息
    model = Column(String(100))
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemImageSetting(Base):
    """系统镜像设置 - 支持可配置的镜像模板"""
    __tablename__ = "system_image_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_type = Column(String(50), unique=True, nullable=False)  # openclaw, ubuntu, webtop, debian, centos, custom
    display_name = Column(String(100), nullable=False)
    image = Column(String(500), nullable=False)  # 镜像地址
    is_enabled = Column(Boolean, default=True)
    description = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserQuota(Base):
    """用户配额"""
    __tablename__ = "user_quotas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID(), ForeignKey("users.id"), unique=True, nullable=False)
    
    # 最大实例数
    max_instances = Column(Integer, default=5)
    
    # CPU配额 (核心数)
    max_cpu_cores = Column(Integer, default=16)
    
    # 内存配额 (GB)
    max_memory_gb = Column(Integer, default=64)
    
    # 存储配额 (GB)
    max_storage_gb = Column(Integer, default=500)
    
    # GPU配额
    max_gpu_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="quota")