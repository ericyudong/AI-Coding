"""Version compare orchestration: diff + LLM interpretation."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cms_models import ContractVersion
from app.services.diff_service import diff_contract_versions, summarize_diff_stats
from app.services.llm_service import interpret_diff


async def compare_versions(db: AsyncSession, contract_id: int, left_id: int, right_id: int) -> dict:
    if left_id == right_id:
        raise ValueError("请选择两个不同的版本进行对比")

    left = await db.get(ContractVersion, left_id)
    right = await db.get(ContractVersion, right_id)
    if not left or not right:
        raise ValueError("版本不存在")
    if left.contract_id != contract_id or right.contract_id != contract_id:
        raise ValueError("版本不属于当前合同")
    if left.contract_id != right.contract_id:
        raise ValueError("只能对比同一份合同下的版本")

    raw_changes = diff_contract_versions(left.content or "", right.content or "")
    stats = summarize_diff_stats(raw_changes)

    change_dicts = [
        {
            "change_type": c.change_type,
            "section": c.section,
            "left_text": c.left_text,
            "right_text": c.right_text,
            "detail": c.detail,
        }
        for c in raw_changes
    ]

    ai_notes, risk_note = await interpret_diff(change_dicts, left.version, right.version)

    changes = []
    for i, c in enumerate(raw_changes):
        note = ai_notes[i] if i < len(ai_notes) else None
        changes.append(
            {
                "change_type": c.change_type,
                "section": c.section,
                "left_text": c.left_text,
                "right_text": c.right_text,
                "detail": c.detail,
                "ai_note": note or c.detail or None,
            }
        )

    return {
        "summary": stats,
        "changes": changes,
        "risk_note": risk_note,
    }


async def compare_texts(
    left_text: str,
    right_text: str,
    *,
    left_label: str = "原始版",
    right_label: str = "修订版",
) -> dict:
    raw_changes = diff_contract_versions(left_text or "", right_text or "")
    stats = summarize_diff_stats(raw_changes)

    change_dicts = [
        {
            "change_type": c.change_type,
            "section": c.section,
            "left_text": c.left_text,
            "right_text": c.right_text,
            "detail": c.detail,
        }
        for c in raw_changes
    ]

    ai_notes, risk_note = await interpret_diff(change_dicts, left_label, right_label)

    changes = []
    for i, c in enumerate(raw_changes):
        note = ai_notes[i] if i < len(ai_notes) else None
        changes.append(
            {
                "change_type": c.change_type,
                "section": c.section,
                "left_text": c.left_text,
                "right_text": c.right_text,
                "detail": c.detail,
                "ai_note": note or c.detail or None,
            }
        )

    return {
        "summary": stats,
        "changes": changes,
        "risk_note": risk_note,
    }
