"""
E-Claw AI Gateway API
模型管理、聊天完成、审计追踪、成本分析、风险控制
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.models import User, UserRole
from app.services.llm_gateway_service import (
    ai_gateway, 
    llm_model_service, 
    risk_rule_service, 
    model_invocation_service,
    ProviderType,
    RiskCategory,
    RiskAction
)

router = APIRouter()


# ============== 请求/响应模型 ==============

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """聊天完成请求"""
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = 2000


class ChatCompletionResponse(BaseModel):
    """聊天完成响应"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    trace_id: str


class LLMModelCreate(BaseModel):
    """创建LLM模型"""
    provider_type: str
    display_name: str
    model_name: str
    endpoint: str
    api_key_ref: str = ""
    is_secure: bool = False
    is_active: bool = True
    input_price: float = 0
    output_price: float = 0
    currency: str = "USD"


class LLMModelUpdate(BaseModel):
    """更新LLM模型"""
    display_name: Optional[str] = None
    endpoint: Optional[str] = None
    api_key_ref: Optional[str] = None
    is_secure: Optional[bool] = None
    is_active: Optional[bool] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    currency: Optional[str] = None


class RiskRuleCreate(BaseModel):
    """创建风险规则"""
    name: str
    rule_type: str = "regex"
    pattern: str
    category: str
    action: str = "block"
    is_active: bool = True
    priority: int = 100
    description: str = ""


class RiskRuleUpdate(BaseModel):
    """更新风险规则"""
    name: Optional[str] = None
    pattern: Optional[str] = None
    category: Optional[str] = None
    action: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class RiskRuleTest(BaseModel):
    """测试风险规则"""
    rule_id: str
    text: str


# ============== AI Gateway 接口 ==============

@router.post("/gateway/llm/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """AI聊天完成接口（OpenAI兼容）"""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    result = await ai_gateway.chat_completions(
        messages=messages,
        model=request.model,
        user_id=str(current_user.id) if current_user else None,
        temperature=request.temperature,
        max_tokens=request.max_tokens or 2000
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    
    return result


@router.get("/gateway/llm/models")
async def list_models(
    provider: Optional[str] = Query(None, description="提供商类型"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取可用模型列表"""
    models = llm_model_service.list_models(provider=provider, is_active=is_active)
    return models


@router.get("/gateway/llm/models/{model_id}")
async def get_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取模型详情"""
    model = llm_model_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/gateway/llm/models")
async def create_model(
    request: LLMModelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """创建模型"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    model = llm_model_service.create_model(request.model_dump())
    return model


@router.put("/gateway/llm/models/{model_id}")
async def update_model(
    model_id: str,
    request: LLMModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新模型"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    model = llm_model_service.update_model(model_id, request.model_dump(exclude_unset=True))
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/gateway/llm/models/{model_id}")
async def delete_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除模型"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin only")
    
    success = llm_model_service.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": "Model deleted successfully"}


# ============== 风险规则接口 ==============

@router.get("/gateway/risk-rules")
async def list_risk_rules(
    category: Optional[str] = Query(None, description="风险类别"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取风险规则列表"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    rules = risk_rule_service.list_rules(category=category, is_active=is_active)
    return rules


@router.post("/gateway/risk-rules")
async def create_risk_rule(
    request: RiskRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """创建风险规则"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin only")
    
    rule = risk_rule_service.create_rule(request.model_dump())
    return rule


@router.put("/gateway/risk-rules/{rule_id}")
async def update_risk_rule(
    rule_id: str,
    request: RiskRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新风险规则"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin only")
    
    rule = risk_rule_service.update_rule(rule_id, request.model_dump(exclude_unset=True))
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.delete("/gateway/risk-rules/{rule_id}")
async def delete_risk_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除风险规则"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin only")
    
    success = risk_rule_service.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted successfully"}


@router.post("/gateway/risk-rules/test")
async def test_risk_rule(
    request: RiskRuleTest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """测试风险规则"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    result = risk_rule_service.test_rule(request.rule_id, request.text)
    return result


# ============== 审计和成本接口 ==============

@router.get("/gateway/audit")
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="用户ID"),
    model_id: Optional[str] = Query(None, description="模型ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取AI审计日志"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS, UserRole.DEPT_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    # 非超级管理员只能查看自己的记录
    if current_user.role != UserRole.SUPER_ADMIN:
        user_id = str(current_user.id)
    
    result = model_invocation_service.list_invocations(
        user_id=user_id,
        model_id=model_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size
    )
    return result


@router.get("/gateway/audit/{trace_id}")
async def get_audit_detail(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取审计详情"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(status_code=403, detail="Admin or ops only")
    
    # 搜索trace_id
    for inv in model_invocation_service.invocations:
        if inv.get("trace_id") == trace_id:
            return inv
    
    raise HTTPException(status_code=404, detail="Trace not found")


@router.get("/gateway/costs")
async def get_costs(
    user_id: Optional[str] = Query(None, description="用户ID"),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取成本统计"""
    # 非超级管理员只能查看自己的
    if current_user.role != UserRole.SUPER_ADMIN:
        user_id = str(current_user.id)
    
    stats = model_invocation_service.get_stats(user_id=user_id, days=days)
    return stats


# ============== 系统设置接口 ==============

@router.get("/gateway/providers")
async def get_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取支持的LLM提供商列表"""
    providers = [
        {"value": ProviderType.OPENAI, "label": "OpenAI"},
        {"value": ProviderType.OPENROUTER, "label": "OpenRouter"},
        {"value": ProviderType.DEEPSEEK, "label": "DeepSeek"},
        {"value": ProviderType.SILICONFLOW, "label": "SiliconFlow"},
        {"value": ProviderType.MOONSHOT, "label": "Moonshot (Kimi)"},
        {"value": ProviderType.ZHIPU, "label": "Zhipu AI (智谱)"},
        {"value": ProviderType.DASHSCOPE, "label": "Alibaba DashScope (通义)"},
        {"value": ProviderType.VOLCENGINE, "label": "Volcengine (火山引擎)"},
        {"value": ProviderType.XAI, "label": "xAI (Grok)"},
        {"value": ProviderType.TOGETHER, "label": "Together AI"},
        {"value": ProviderType.FIREWORKS, "label": "Fireworks AI"},
        {"value": ProviderType.PERPLEXITY, "label": "Perplexity AI"},
        {"value": ProviderType.LOCAL, "label": "Local/Internal"}
    ]
    return providers


@router.get("/gateway/risk-categories")
async def get_risk_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取风险类别列表"""
    categories = [
        {"value": RiskCategory.PRIVACY, "label": "隐私数据"},
        {"value": RiskCategory.FINANCE, "label": "金融数据"},
        {"value": RiskCategory.SECURITY, "label": "安全风险"},
        {"value": RiskCategory.COMPLIANCE, "label": "合规风险"}
    ]
    return categories