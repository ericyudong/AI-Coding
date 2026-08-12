"""Extract structured contract fields from plain text (rules + optional LLM)."""
import json
import re
from datetime import date


def _find_amount(text: str) -> float:
    patterns = [
        r"合同总?金额[为:]?\s*[人民币¥]?\s*([\d,，.]+)\s*[万元]?",
        r"金额[为:]?\s*[人民币¥]?\s*([\d,，.]+)\s*[万元]?",
        r"[¥￥]\s*([\d,，.]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            raw = m.group(1).replace(",", "").replace("，", "")
            try:
                val = float(raw)
                if "万" in text[m.start() : m.end() + 5]:
                    val *= 10000
                return val
            except ValueError:
                continue
    return 0.0


def _find_party(text: str, label: str) -> str:
    m = re.search(rf"{label}[：:]\s*([^\n，,；;]+)", text)
    return m.group(1).strip() if m else ""


def _find_date(text: str, label: str) -> str | None:
    m = re.search(
        rf"{label}[：:]?\s*(\d{{4}}[-/年]\d{{1,2}}[-/月]\d{{1,2}})",
        text,
    )
    if not m:
        return None
    raw = m.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    parts = raw.split("-")
    if len(parts) >= 3:
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat()
        except ValueError:
            return None
    return None


def _detect_contract_type(text: str) -> str:
    mapping = {
        "采购": "purchase",
        "销售": "sales",
        "租赁": "lease",
        "劳务": "labor",
        "保密": "nda",
        "技术开发": "tech",
        "开发": "tech",
    }
    for kw, t in mapping.items():
        if kw in text[:500]:
            return t
    return "other"


def _detect_tags(text: str) -> list[str]:
    tags = ["AI导入"]
    if "保密" in text:
        tags.append("有保密条款")
    if "续签" in text or "自动续" in text:
        tags.append("自动续签")
    if _find_amount(text) >= 1_000_000:
        tags.append("金额>100万")
    return tags


def _detect_key_clauses(text: str) -> list[str]:
    clauses: list[str] = []
    if re.search(r"付款|支付", text):
        clauses.append("付款条款: 见合同正文")
    if re.search(r"违约", text):
        clauses.append("违约责任: 见合同正文")
    if "仲裁" in text or "诉讼" in text:
        clauses.append("争议解决: 见合同正文")
    if "保密" in text:
        clauses.append("保密条款: 有")
    if "续签" in text:
        clauses.append("续签条款: 见合同正文")
    return clauses or ["（待人工确认关键条款）"]


def extract_fields_from_text(text: str, filename: str = "") -> dict:
    """Rule-based field extraction from contract text."""
    name = filename
    if not name or name == "unknown":
        first_line = text.strip().split("\n")[0][:80] if text else "导入合同"
        name = first_line or "导入合同"

    party_a = _find_party(text, "甲方") or "益慧科技有限公司"
    party_b = _find_party(text, "乙方")
    amount = _find_amount(text)

    return {
        "name": name.replace(".pdf", "").replace(".docx", "").replace(".doc", "")[:256],
        "contract_type": _detect_contract_type(text),
        "party_a": party_a,
        "party_b": party_b,
        "amount": amount,
        "sign_date": _find_date(text, "签订日期") or _find_date(text, "签署日期"),
        "effective_date": _find_date(text, "生效日期") or _find_date(text, "生效日"),
        "expire_date": _find_date(text, "到期") or _find_date(text, "终止日期"),
        "key_clauses": _detect_key_clauses(text),
        "tags": _detect_tags(text),
        "content_text": text,
    }


async def extract_fields_with_llm(text: str, filename: str) -> dict:
    """Try LLM extraction, fallback to rules."""
    from app.services.llm_service import extract_contract_fields

    llm_result = await extract_contract_fields(text[:12000], filename)
    if llm_result:
        base = extract_fields_from_text(text, filename)
        base.update({k: v for k, v in llm_result.items() if v})
        base["content_text"] = text
        return base
    result = extract_fields_from_text(text, filename)
    result["_rule_only"] = True
    return result


def fields_to_json(fields: dict) -> str:
    return json.dumps(fields, ensure_ascii=False)
