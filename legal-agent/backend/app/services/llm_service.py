"""LLM integration with mock fallback."""
import json
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SEARCH_PROMPTS = {
    "comprehensive": "你是一名资深法律顾问，请对以下法律问题进行综合分析，给出结论、法律依据与实务建议：",
    "regulation": "你是一名法规检索专家，请检索并解读与以下问题相关的法律法规条文：",
    "case": "你是一名类案检索专家，请分析以下问题相关的司法裁判观点与类案：",
    "penalty": "你是一名行政处罚领域专家，请分析以下问题涉及的行政处罚规定与案例：",
    "interpretation": "你是一名法律专业解读专家，请对以下问题进行深度专业解读：",
}

MODULE_PROMPTS = {
    "labor_law": "你是一名劳动法专家，请基于中国劳动法律法规，准确、专业地回答用户问题，并在回答末尾列出主要法律依据：",
    "qa": "你是一名企业法务顾问，请专业、清晰地回答以下法律问题：",
    "financial": "你是一名金融合规专家，请从合规角度回答以下问题：",
    "overseas": "你是一名企业出海法务专家，请结合跨境合规要求回答以下问题：",
}

REVIEW_PROMPTS = {
    "checklist": (
        "你是一名资深合同审核律师。请按审核清单从以下维度逐项审核："
        "主体资质、权利义务、付款/交付、违约责任、保密、知识产权、争议解决、合规风险。"
        "输出 Markdown：审核摘要、分项意见、风险等级(高/中/低)、修改建议。"
    ),
    "reference": (
        "你是一名资深合同审核律师。请参照标准商业合同惯例审核以下合同，"
        "指出与惯例不一致之处及潜在风险。输出 Markdown 格式审核报告。"
    ),
}


def _mock_search_answer(query: str, search_type: str) -> str:
    labels = {
        "comprehensive": "综合分析",
        "regulation": "法规查询",
        "case": "类案检索",
        "penalty": "行政处罚",
        "interpretation": "专业解读",
    }
    label = labels.get(search_type, "综合分析")
    return (
        f"【{label}】关于「{query}」的初步分析：\n\n"
        "1. **结论**：需结合具体事实与最新法规进一步判断。\n"
        "2. **法律依据**：建议检索《民法典》《劳动法》《公司法》等相关条文。\n"
        "3. **实务建议**：建议补充合同文本、时间节点、主体资质等关键信息后再做精准判断。\n\n"
        "（当前为演示模式，配置 OPENAI_API_KEY 后可获得 AI 生成的完整分析。）"
    )


def _mock_chat_answer(message: str, module: str) -> str:
    module_names = {
        "labor_law": "劳动法",
        "qa": "法律问答",
        "financial": "金融合规",
        "overseas": "企业出海",
    }
    name = module_names.get(module, "法律")
    return (
        f"【{name}】关于您的问题「{message[:100]}{'...' if len(message) > 100 else ''}」：\n\n"
        "根据现行法律规定，需结合具体事实进行判断。一般而言，用人单位与劳动者之间的权利义务"
        "应遵循合法、公平、平等自愿、协商一致、诚实信用原则。\n\n"
        "**参考依据**：《中华人民共和国劳动合同法》第三条、第三十九条等。\n\n"
        "（当前为演示模式，配置 OPENAI_API_KEY 后可获得更精准的 AI 回答。）"
    )


def _mock_contract_draft(purpose: str, position: str, extra_info: str, style: str) -> str:
    return (
        f"# 合同草案\n\n"
        f"**起草风格**：{style}\n\n"
        f"## 第一条 合同目的\n{purpose}\n\n"
        f"## 第二条 合同主体\n"
        f"甲方（{position or '一方'}）：_______________\n"
        f"乙方：_______________\n\n"
        f"## 第三条 主要条款\n"
        f"{extra_info or '（待补充具体条款）'}\n\n"
        f"## 第四条 违约责任\n"
        f"任何一方违反本合同约定，应承担相应的违约责任。\n\n"
        f"## 第五条 争议解决\n"
        f"因本合同引起的争议，双方应协商解决；协商不成的，提交有管辖权的人民法院诉讼解决。\n\n"
        f"---\n"
        f"（当前为演示模式，配置 OPENAI_API_KEY 后可生成完整合同文本。）"
    )


def _mock_contract_review(filename: str, content_preview: str = "") -> str:
    preview_note = f"\n\n> 已解析正文 {len(content_preview)} 字" if content_preview else ""
    return (
        f"# 合同审核报告\n\n"
        f"**文件**：{filename}{preview_note}\n\n"
        f"## 审核摘要\n"
        f"- 合同主体信息：建议核实营业执照与授权文件\n"
        f"- 权利义务条款：整体结构完整，建议明确交付标准\n"
        f"- 违约责任：建议补充具体违约金计算方式\n"
        f"- 争议解决：管辖约定有效\n\n"
        f"## 风险等级\n"
        f"**中等** — 共发现 3 处建议修改项\n\n"
        f"（当前为演示模式，配置 OPENAI_API_KEY 后可进行 AI 深度审核。）"
    )


def _mock_diff_interpret(changes: list[dict]) -> tuple[list[str | None], str]:
    notes = []
    for c in changes:
        detail = str(c.get("detail") or "").strip()
        if detail:
            notes.append(detail)
            continue
        if c["change_type"] == "modified":
            notes.append(f"{c['section']}内容变更")
        elif c["change_type"] == "added":
            notes.append(f"新增{c['section']}")
        elif c["change_type"] == "removed":
            notes.append(f"删除{c['section']}")
        else:
            notes.append("条款变更")
    risk = f"共检测到 {len(changes)} 处变更，建议法务重点复核修改项。" if changes else "两版本无显著差异。"
    return notes, risk


async def _call_llm(system: str, user: str, temperature: float = 0.3) -> str | None:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        return None
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.warning("LLM API error %s: %s", resp.status_code, resp.text[:300])
                return None
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                logger.warning("LLM API error: %s", data.get("error"))
                return None
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None


async def legal_search(query: str, search_type: str) -> tuple[str, list[str]]:
    system = SEARCH_PROMPTS.get(search_type, SEARCH_PROMPTS["comprehensive"])
    answer = await _call_llm(system, query)
    if answer is None:
        answer = _mock_search_answer(query, search_type)
    refs = [
        "《中华人民共和国民法典》",
        "《中华人民共和国劳动合同法》",
        "最高人民法院相关司法解释",
    ]
    return answer, refs


async def chat_reply(message: str, module: str) -> str:
    system = MODULE_PROMPTS.get(module, MODULE_PROMPTS["qa"])
    answer = await _call_llm(system, message)
    return answer or _mock_chat_answer(message, module)


async def draft_contract(
    purpose: str, position: str, extra_info: str, style: str, draft_type: str
) -> str:
    if draft_type == "clause":
        user = f"请生成合同条款。合同目的：{purpose}。我方立场：{position}。其他信息：{extra_info}。风格：{style}"
        system = "你是一名专业合同律师，请生成规范、可落地的合同条款。"
    else:
        user = (
            f"请起草一份完整合同。\n"
            f"合同目的：{purpose}\n"
            f"我方立场：{position}\n"
            f"其他信息：{extra_info}\n"
            f"起草风格：{style}"
        )
        system = "你是一名专业合同律师，请生成结构完整、条款规范的中文合同。"
    answer = await _call_llm(system, user)
    return answer or _mock_contract_draft(purpose, position, extra_info, style)


async def review_contract(
    filename: str,
    content_text: str = "",
    review_mode: str = "checklist",
) -> str:
    settings = get_settings()
    system = REVIEW_PROMPTS.get(review_mode, REVIEW_PROMPTS["checklist"])

    if not content_text.strip():
        answer = await _call_llm(
            system,
            f"请审核合同文件「{filename}」。注意：未能提取正文，请基于文件名给出通用审核建议。",
        )
        return answer or _mock_contract_review(filename)

    text = content_text
    if len(text) > settings.review_max_chars:
        from app.services.text_chunker import chunk_contract_text

        chunks = chunk_contract_text(text, chunk_size=settings.review_chunk_size)
        parts = []
        for i, ch in enumerate(chunks[:6]):
            part = await _call_llm(
                system,
                f"文件名：{filename}\n这是合同第 {i + 1}/{min(len(chunks), 6)} 部分，请审核：\n\n{ch.content}",
            )
            parts.append(part or f"（第{i + 1}部分演示审核：建议关注权利义务与违约责任条款）")
        merged = await _call_llm(
            "你是一名合同审核律师，请将以下分段审核意见合并为一份完整 Markdown 审核报告。",
            "\n\n---\n\n".join(parts),
        )
        return merged or _mock_contract_review(filename, content_text)

    user = f"文件名：{filename}\n\n合同正文：\n{text}"
    answer = await _call_llm(system, user)
    return answer or _mock_contract_review(filename, content_text)


async def extract_contract_fields(text: str, filename: str) -> dict | None:
    system = (
        "你是合同信息抽取专家。从合同文本中提取 JSON 字段："
        "name, contract_type(purchase/sales/lease/labor/nda/tech/other), "
        "party_a, party_b, amount(数字), sign_date, effective_date, expire_date (ISO日期或null), "
        "key_clauses(字符串数组)。仅输出 JSON，不要其他文字。"
    )
    user = f"文件名：{filename}\n\n{text[:8000]}"
    raw = await _call_llm(system, user, temperature=0.1)
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None
    return None


async def generate_contract_detail_summary(
    name: str,
    content: str,
    metadata: dict,
) -> list[str] | None:
    system = (
        "你是资深法务合同分析师。根据合同全文生成详细摘要。"
        '输出 JSON：{"items": ["...", ...]}，8-12条，每条40-150字。'
        "须覆盖：合同性质、双方、标的/服务、金额与计费、服务期限、付款与交付、"
        "核心权利义务、数据/保密/知识产权、违约责任、争议解决。"
        "仅依据合同文本，不得编造合同中不存在的内容。"
    )
    user = (
        f"合同名称：{name}\n"
        f"元数据：{json.dumps(metadata, ensure_ascii=False)}\n\n"
        f"合同正文：\n{content[:10000]}"
    )
    raw = await _call_llm(system, user, temperature=0.2)
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start:end])
        items = data.get("items", [])
        if isinstance(items, list):
            cleaned = [str(item).strip() for item in items if str(item).strip()]
            if cleaned:
                return cleaned
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return None


async def rag_answer(contract_name: str, context: str, question: str) -> str | None:
    system = (
        "你是合同问答助手。仅根据提供的合同条款片段回答，不得编造。"
        "若片段不足以回答，明确说明。回答末尾用 [引用: 条款标题] 标注来源。"
    )
    user = f"合同名称：{contract_name}\n\n相关条款：\n{context}\n\n用户问题：{question}"
    return await _call_llm(system, user, temperature=0.2)


async def interpret_diff(
    changes: list[dict],
    left_version: str,
    right_version: str,
) -> tuple[list[str | None], str]:
    if not changes:
        return [], "两版本内容一致，未检测到差异。"

    system = (
        "你是合同法务专家。根据版本差异列表，为每条变更给出简短语义说明（ai_note），"
        "并给出一段总体风险摘要 risk_note。输出 JSON："
        '{"notes": ["说明1", ...], "risk_note": "..."}'
    )
    user = json.dumps(
        {"left": left_version, "right": right_version, "changes": changes[:15]},
        ensure_ascii=False,
    )
    raw = await _call_llm(system, user, temperature=0.2)
    if raw:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            notes = data.get("notes", [])
            while len(notes) < len(changes):
                notes.append(None)
            return notes[: len(changes)], data.get("risk_note", "")
        except (json.JSONDecodeError, ValueError):
            pass
    return _mock_diff_interpret(changes)


async def parse_search_natural_language(q: str) -> tuple[list[dict], str]:
    """Parse NL search into structured filters. Returns (filters, keyword_remainder)."""
    system = (
        "你是合同检索助手。将用户的自然语言搜索解析为 JSON："
        '{"filters":[{"field":"amount|status|contract_type|sign_date_year|party_b|name","operator":"eq|gt|gte|lt|lte|contains","value":"..."}],'
        '"keywords":"剩余关键词"}'
        "金额单位万请转为数字字符串（如50万->500000）。状态映射：履行中=active，待签署=pending_sign。"
        "合同类型：采购=purchase，销售=sales，租赁=lease。仅输出 JSON。"
    )
    raw = await _call_llm(system, q, temperature=0.1)
    if not raw:
        return [], q
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        filters = data.get("filters") or []
        keywords = str(data.get("keywords") or "").strip()
        normalized = []
        for f in filters:
            if isinstance(f, dict) and f.get("field") and f.get("value") is not None:
                normalized.append(
                    {
                        "field": str(f["field"]),
                        "operator": str(f.get("operator") or "eq"),
                        "value": str(f["value"]),
                    }
                )
        return normalized, keywords or q
    except (json.JSONDecodeError, ValueError, TypeError):
        return [], q
