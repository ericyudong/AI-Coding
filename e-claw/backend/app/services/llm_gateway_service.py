"""
E-Claw AI Gateway 服务
支持多提供商模型管理、审计追踪、成本计算、风险控制
"""
import os
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import re

# LLM 提供商类型
class ProviderType(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    MOONSHOT = "moonshot"
    ZHIPU = "zhipu"
    DASHSCOPE = "dashscope"
    VOLCENGINE = "volcengine"
    XAI = "xai"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    PERPLEXITY = "perplexity"
    LOCAL = "local"


# 风险规则类型
class RiskCategory(str, Enum):
    PRIVACY = "privacy"
    FINANCE = "finance"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class RiskAction(str, Enum):
    BLOCK = "block"
    ROUTE_SECURE_MODEL = "route_secure_model"
    ALERT = "alert"


class LLMModel:
    """LLM模型"""
    def __init__(self):
        self.models: List[Dict[str, Any]] = []
        self._init_default_models()
    
    def _init_default_models(self):
        """初始化默认模型"""
        self.models = [
            {
                "id": "gpt-4",
                "provider_type": ProviderType.OPENAI,
                "display_name": "GPT-4",
                "model_name": "gpt-4",
                "endpoint": "https://api.openai.com/v1",
                "api_key_ref": "OPENAI_API_KEY",
                "is_secure": False,
                "is_active": True,
                "input_price": 0.03,
                "output_price": 0.06,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "gpt-3.5-turbo",
                "provider_type": ProviderType.OPENAI,
                "display_name": "GPT-3.5 Turbo",
                "model_name": "gpt-3.5-turbo",
                "endpoint": "https://api.openai.com/v1",
                "api_key_ref": "OPENAI_API_KEY",
                "is_secure": False,
                "is_active": True,
                "input_price": 0.001,
                "output_price": 0.002,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "deepseek-chat",
                "provider_type": ProviderType.DEEPSEEK,
                "display_name": "DeepSeek Chat",
                "model_name": "deepseek-chat",
                "endpoint": "https://api.deepseek.com/v1",
                "api_key_ref": "DEEPSEEK_API_KEY",
                "is_secure": False,
                "is_active": True,
                "input_price": 0.001,
                "output_price": 0.002,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "qwen-turbo",
                "provider_type": ProviderType.DASHSCOPE,
                "display_name": "通义千问 Turbo",
                "model_name": "qwen-turbo",
                "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key_ref": "DASHSCOPE_API_KEY",
                "is_secure": True,
                "is_active": True,
                "input_price": 0.001,
                "output_price": 0.002,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "glm-4",
                "provider_type": ProviderType.ZHIPU,
                "display_name": "GLM-4",
                "model_name": "glm-4",
                "endpoint": "https://open.bigmodel.cn/api/paas/v4",
                "api_key_ref": "ZHIPU_API_KEY",
                "is_secure": True,
                "is_active": True,
                "input_price": 0.001,
                "output_price": 0.001,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "kimi-k1.5",
                "provider_type": ProviderType.MOONSHOT,
                "display_name": "Kimi k1.5",
                "model_name": "kimi-k1.5",
                "endpoint": "https://api.moonshot.cn/v1",
                "api_key_ref": "MOONSHOT_API_KEY",
                "is_secure": True,
                "is_active": True,
                "input_price": 0.015,
                "output_price": 0.015,
                "currency": "USD",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        ]
    
    def list_models(self, provider: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取模型列表"""
        result = self.models.copy()
        
        if provider:
            result = [m for m in result if m["provider_type"] == provider]
        
        if is_active is not None:
            result = [m for m in result if m["is_active"] == is_active]
        
        return result
    
    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取模型详情"""
        for model in self.models:
            if model["id"] == model_id:
                return model
        return None
    
    def create_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建模型"""
        model_id = str(uuid.uuid4())
        model = {
            "id": model_id,
            "provider_type": model_data.get("provider_type"),
            "display_name": model_data.get("display_name"),
            "model_name": model_data.get("model_name"),
            "endpoint": model_data.get("endpoint"),
            "api_key_ref": model_data.get("api_key_ref", ""),
            "is_secure": model_data.get("is_secure", False),
            "is_active": model_data.get("is_active", True),
            "input_price": model_data.get("input_price", 0),
            "output_price": model_data.get("output_price", 0),
            "currency": model_data.get("currency", "USD"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        self.models.append(model)
        return model
    
    def update_model(self, model_id: str, model_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新模型"""
        for i, model in enumerate(self.models):
            if model["id"] == model_id:
                model.update(model_data)
                model["updated_at"] = datetime.utcnow().isoformat()
                return model
        return None
    
    def delete_model(self, model_id: str) -> bool:
        """删除模型"""
        for i, model in enumerate(self.models):
            if model["id"] == model_id:
                self.models.pop(i)
                return True
        return False
    
    def get_active_model(self, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取活动模型"""
        if display_name:
            for model in self.models:
                if model["is_active"] and model["display_name"] == display_name:
                    return model
        
        # 返回第一个非安全模型
        for model in self.models:
            if model["is_active"] and not model["is_secure"]:
                return model
        
        return None
    
    def get_secure_model(self) -> Optional[Dict[str, Any]]:
        """获取安全模型"""
        for model in self.models:
            if model["is_active"] and model["is_secure"]:
                return model
        return None


class RiskRule:
    """风险规则"""
    def __init__(self):
        self.rules: List[Dict[str, Any]] = []
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        self.rules = [
            {
                "id": "rule-1",
                "name": "信用卡号检测",
                "rule_type": "regex",
                "pattern": r"\b(?:\d[ -]*?){13,16}\b",
                "category": RiskCategory.FINANCE,
                "action": RiskAction.BLOCK,
                "is_active": True,
                "priority": 1,
                "description": "检测信用卡号",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "rule-2",
                "name": "身份证号检测",
                "rule_type": "regex",
                "pattern": r"\b\d{17}[\dXx]\b",
                "category": RiskCategory.PRIVACY,
                "action": RiskAction.BLOCK,
                "is_active": True,
                "priority": 1,
                "description": "检测身份证号",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "rule-3",
                "name": "手机号检测",
                "rule_type": "regex",
                "pattern": r"\b1[3-9]\d{9}\b",
                "category": RiskCategory.PRIVACY,
                "action": RiskAction.BLOCK,
                "is_active": True,
                "priority": 2,
                "description": "检测手机号",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "rule-4",
                "name": "敏感企业数据",
                "rule_type": "regex",
                "pattern": r"(?:密码|密钥|token|secret|key)[\s:=]+[\w-]+",
                "category": RiskCategory.SECURITY,
                "action": RiskAction.BLOCK,
                "is_active": True,
                "priority": 1,
                "description": "检测敏感密钥信息",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            },
            {
                "id": "rule-5",
                "name": "SQL注入检测",
                "rule_type": "regex",
                "pattern": r"(?:union|select|insert|delete|drop|update|create)\s+",
                "category": RiskCategory.SECURITY,
                "action": RiskAction.ROUTE_SECURE_MODEL,
                "is_active": True,
                "priority": 2,
                "description": "检测SQL注入尝试",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        ]
    
    def list_rules(self, category: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取规则列表"""
        result = self.rules.copy()
        
        if category:
            result = [r for r in result if r["category"] == category]
        
        if is_active is not None:
            result = [r for r in result if r["is_active"] == is_active]
        
        # 按优先级排序
        result.sort(key=lambda x: x["priority"])
        
        return result
    
    def create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建规则"""
        rule_id = f"rule-{uuid.uuid4().hex[:8]}"
        rule = {
            "id": rule_id,
            "name": rule_data.get("name"),
            "rule_type": rule_data.get("rule_type", "regex"),
            "pattern": rule_data.get("pattern"),
            "category": rule_data.get("category"),
            "action": rule_data.get("action", RiskAction.BLOCK),
            "is_active": rule_data.get("is_active", True),
            "priority": rule_data.get("priority", 100),
            "description": rule_data.get("description", ""),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        self.rules.append(rule)
        return rule
    
    def update_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新规则"""
        for i, rule in enumerate(self.rules):
            if rule["id"] == rule_id:
                rule.update(rule_data)
                rule["updated_at"] = datetime.utcnow().isoformat()
                return rule
        return None
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        for i, rule in enumerate(self.rules):
            if rule["id"] == rule_id:
                self.rules.pop(i)
                return True
        return False
    
    def test_rule(self, rule_id: str, text: str) -> Dict[str, Any]:
        """测试规则"""
        for rule in self.rules:
            if rule["id"] == rule_id:
                try:
                    pattern = rule["pattern"]
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    return {
                        "rule_id": rule_id,
                        "matched": len(matches) > 0,
                        "match_count": len(matches),
                        "matches": matches[:10]  # 最多返回10个匹配
                    }
                except Exception as e:
                    return {
                        "rule_id": rule_id,
                        "matched": False,
                        "error": str(e)
                    }
        return {"error": "Rule not found"}
    
    def scan_text(self, text: str) -> List[Dict[str, Any]]:
        """扫描文本"""
        hits = []
        
        # 按优先级排序
        sorted_rules = sorted(self.rules, key=lambda x: x["priority"])
        
        for rule in sorted_rules:
            if not rule["is_active"]:
                continue
            
            try:
                pattern = rule["pattern"]
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    hits.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "category": rule["category"],
                        "action": rule["action"],
                        "matched_text": matches[0],
                        "match_count": len(matches)
                    })
            except Exception:
                pass
        
        return hits


class ModelInvocation:
    """模型调用记录"""
    def __init__(self):
        self.invocations: List[Dict[str, Any]] = []
    
    def add_invocation(self, invocation: Dict[str, Any]) -> Dict[str, Any]:
        """添加调用记录"""
        record = {
            "id": str(uuid.uuid4()),
            "trace_id": invocation.get("trace_id", str(uuid.uuid4())),
            "user_id": invocation.get("user_id"),
            "instance_id": invocation.get("instance_id"),
            "model_id": invocation.get("model_id"),
            "model_name": invocation.get("model_name"),
            "provider_type": invocation.get("provider_type"),
            "request_tokens": invocation.get("request_tokens", 0),
            "response_tokens": invocation.get("response_tokens", 0),
            "total_tokens": invocation.get("total_tokens", 0),
            "reasoning_tokens": invocation.get("reasoning_tokens", 0),
            "status": invocation.get("status", "success"),
            "error_message": invocation.get("error_message"),
            "cost": invocation.get("cost", 0),
            "created_at": datetime.utcnow().isoformat()
        }
        self.invocations.append(record)
        return record
    
    def list_invocations(
        self,
        user_id: Optional[str] = None,
        model_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """查询调用记录"""
        result = self.invocations.copy()
        
        if user_id:
            result = [i for i in result if i.get("user_id") == user_id]
        
        if model_id:
            result = [i for i in result if i.get("model_id") == model_id]
        
        if start_date:
            result = [i for i in result if i.get("created_at", "") >= start_date]
        
        if end_date:
            result = [i for i in result if i.get("created_at", "") <= end_date]
        
        # 按时间倒序
        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # 分页
        total = len(result)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = result[start:end]
        
        return {
            "invocations": paginated,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    def get_stats(self, user_id: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """获取统计数据"""
        result = self.invocations.copy()
        
        if user_id:
            result = [i for i in result if i.get("user_id") == user_id]
        
        # 计算时间范围
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 过滤时间
        result = [
            i for i in result 
            if datetime.fromisoformat(i.get("created_at", "2000-01-01")) >= start_date
        ]
        
        # 统计
        total_calls = len(result)
        total_tokens = sum(i.get("total_tokens", 0) for i in result)
        total_cost = sum(i.get("cost", 0) for i in result)
        success_calls = len([i for i in result if i.get("status") == "success"])
        failed_calls = total_calls - success_calls
        
        # 按模型分组
        model_stats: Dict[str, Dict[str, Any]] = {}
        for inv in result:
            model_name = inv.get("model_name", "unknown")
            if model_name not in model_stats:
                model_stats[model_name] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost": 0
                }
            model_stats[model_name]["calls"] += 1
            model_stats[model_name]["tokens"] += inv.get("total_tokens", 0)
            model_stats[model_name]["cost"] += inv.get("cost", 0)
        
        return {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "avg_tokens_per_call": total_tokens / total_calls if total_calls > 0 else 0,
            "model_stats": model_stats,
            "period_days": days
        }


# 全局实例
llm_model_service = LLMModel()
risk_rule_service = RiskRule()
model_invocation_service = ModelInvocation()


# AI Gateway 核心逻辑
class AIGateway:
    """AI Gateway 核心"""
    
    def __init__(self):
        self.model_service = llm_model_service
        self.risk_service = risk_rule_service
        self.invocation_service = model_invocation_service
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        user_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """聊天完成接口"""
        trace_id = str(uuid.uuid4())
        
        # 1. 确定使用的模型
        selected_model = None
        
        if model:
            selected_model = self.model_service.get_model(model)
            if not selected_model or not selected_model.get("is_active"):
                return {"error": f"Model {model} not found or inactive"}
        else:
            selected_model = self.model_service.get_active_model()
        
        if not selected_model:
            return {"error": "No available model"}
        
        # 2. 风险扫描
        # 合并消息内容进行扫描
        full_text = " ".join([m.get("content", "") for m in messages])
        risk_hits = self.risk_service.scan_text(full_text)
        
        # 如果有风险命中
        if risk_hits:
            hit = risk_hits[0]
            
            if hit["action"] == RiskAction.BLOCK:
                # 记录风险命中
                self._record_risk_hit(trace_id, hit, user_id)
                
                return {
                    "error": "Content blocked by risk policy",
                    "risk_hit": hit,
                    "trace_id": trace_id
                }
            
            elif hit["action"] == RiskAction.ROUTE_SECURE_MODEL:
                # 切换到安全模型
                secure_model = self.model_service.get_secure_model()
                if secure_model:
                    selected_model = secure_model
        
        # 3. 计算请求token数（简化估算）
        request_tokens = sum(len(m.get("content", "").split()) for m in messages) * 2
        
        # 4. 调用模型（模拟）
        try:
            # 这里应该调用实际的LLM API
            # 为了演示，我们模拟响应
            response_content = self._simulate_response(messages, selected_model)
            response_tokens = len(response_content.split()) * 2
            total_tokens = request_tokens + response_tokens
            
            # 5. 计算成本
            cost = (
                request_tokens / 1000 * selected_model.get("input_price", 0) +
                response_tokens / 1000 * selected_model.get("output_price", 0)
            )
            
            # 6. 记录调用
            self.invocation_service.add_invocation({
                "trace_id": trace_id,
                "user_id": user_id,
                "instance_id": instance_id,
                "model_id": selected_model.get("id"),
                "model_name": selected_model.get("display_name"),
                "provider_type": selected_model.get("provider_type"),
                "request_tokens": request_tokens,
                "response_tokens": response_tokens,
                "total_tokens": total_tokens,
                "status": "success",
                "cost": cost
            })
            
            return {
                "id": f"chatcmpl-{trace_id[:8]}",
                "object": "chat.completion",
                "created": int(datetime.utcnow().timestamp()),
                "model": selected_model.get("model_name"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": request_tokens,
                    "completion_tokens": response_tokens,
                    "total_tokens": total_tokens
                },
                "trace_id": trace_id,
                "cost": cost
            }
            
        except Exception as e:
            # 记录失败
            self.invocation_service.add_invocation({
                "trace_id": trace_id,
                "user_id": user_id,
                "instance_id": instance_id,
                "model_id": selected_model.get("id"),
                "model_name": selected_model.get("display_name"),
                "provider_type": selected_model.get("provider_type"),
                "request_tokens": request_tokens,
                "response_tokens": 0,
                "total_tokens": request_tokens,
                "status": "failed",
                "error_message": str(e)
            })
            
            return {"error": str(e), "trace_id": trace_id}
    
    def _simulate_response(self, messages: List[Dict[str, str]], model: Dict[str, Any]) -> str:
        """模拟LLM响应"""
        last_message = messages[-1].get("content", "") if messages else ""
        
        responses = [
            f"根据您的请求 '{last_message[:50]}...' ，我理解您需要帮助。这是一个模拟响应。",
            f"我收到了您的消息。关于 '{last_message[:30]}...' 的问题，让我来解答。",
            f"感谢您的提问。针对您提到的 '{last_message[:30]}...' ，以下是详细的说明。"
        ]
        
        import random
        return random.choice(responses)
    
    def _record_risk_hit(self, trace_id: str, hit: Dict[str, Any], user_id: Optional[str]):
        """记录风险命中"""
        # 可以扩展到单独的表中
        pass


# 全局AI Gateway实例
ai_gateway = AIGateway()