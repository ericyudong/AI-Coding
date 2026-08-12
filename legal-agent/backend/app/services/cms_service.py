"""Contract Management System business logic."""
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cms_models import ContractImportTask, ContractVersion, ManagedContract

STATUS_LABELS = {
    "pending_sign": "待签署",
    "active": "履行中",
    "expired": "已到期",
    "archived": "已归档",
    "terminated": "已终止",
}

TYPE_LABELS = {
    "purchase": "采购合同",
    "sales": "销售合同",
    "lease": "租赁合同",
    "labor": "劳务合同",
    "nda": "保密协议",
    "tech": "技术开发",
    "other": "其他",
}

SEED_CONTRACTS = [
    {
        "code": "CT-2026-0088",
        "name": "采购合同-供应商A",
        "contract_type": "purchase",
        "party_a": "益慧科技有限公司",
        "party_b": "供应商A有限公司",
        "amount": 5000000,
        "sign_date": date(2026, 3, 15),
        "effective_date": date(2026, 4, 1),
        "expire_date": date(2027, 3, 31),
        "status": "active",
        "owner": "王法务",
        "risk_level": "high",
        "tags": ["采购合同", "高风险", "有保密条款", "自动续签", "金额>100万"],
        "key_clauses": ["付款条款: 签约30%+验收60%+质保10%", "违约责任: 每日0.5‰", "争议解决: 仲裁", "保密条款: 有", "续签条款: 自动续签"],
    },
    {
        "code": "CT-2026-0076",
        "name": "技术开发合同-乙方",
        "contract_type": "tech",
        "party_a": "益慧科技有限公司",
        "party_b": "乙方科技有限公司",
        "amount": 2800000,
        "sign_date": date(2026, 2, 10),
        "effective_date": date(2026, 3, 1),
        "expire_date": date(2027, 6, 15),
        "status": "active",
        "owner": "王法务",
        "risk_level": "medium",
        "tags": ["技术开发", "有保密条款", "中风险"],
        "key_clauses": ["保密条款: 双方另行签订专项保密协议", "知识产权: 归甲方所有"],
    },
    {
        "code": "CT-2026-0065",
        "name": "租赁合同-办公场地",
        "contract_type": "lease",
        "party_a": "益慧科技有限公司",
        "party_b": "XX置业有限公司",
        "amount": 480000,
        "sign_date": date(2025, 12, 1),
        "effective_date": date(2026, 1, 1),
        "expire_date": date(2026, 12, 31),
        "status": "active",
        "owner": "李行政",
        "risk_level": "low",
        "tags": ["租赁合同", "即将到期", "有保密条款"],
        "key_clauses": ["租金: 480000/年", "保密条款: 有"],
    },
    {
        "code": "CT-2026-0054",
        "name": "保密协议-合作伙伴B",
        "contract_type": "nda",
        "party_a": "益慧科技有限公司",
        "party_b": "合作伙伴B有限公司",
        "amount": 0,
        "sign_date": None,
        "effective_date": date(2026, 6, 1),
        "expire_date": date(2028, 1, 1),
        "status": "pending_sign",
        "owner": "王法务",
        "risk_level": "low",
        "tags": ["保密协议", "低风险"],
        "key_clauses": ["保密期限: 3年"],
    },
    {
        "code": "CT-2026-0043",
        "name": "销售合同-客户C",
        "contract_type": "sales",
        "party_a": "益慧科技有限公司",
        "party_b": "客户C集团",
        "amount": 1200000,
        "sign_date": date(2026, 1, 20),
        "effective_date": date(2026, 2, 1),
        "expire_date": date(2026, 9, 30),
        "status": "active",
        "owner": "张业务",
        "risk_level": "medium",
        "tags": ["销售合同", "中风险", "金额>100万"],
        "key_clauses": ["交付周期: 6个月", "验收标准: 双方确认"],
    },
    {
        "code": "CT-2026-0032",
        "name": "劳务合同-咨询顾问",
        "contract_type": "labor",
        "party_a": "益慧科技有限公司",
        "party_b": "咨询顾问张某",
        "amount": 360000,
        "sign_date": date(2025, 4, 1),
        "effective_date": date(2025, 4, 1),
        "expire_date": date(2026, 3, 31),
        "status": "expired",
        "owner": "张业务",
        "risk_level": "low",
        "tags": ["劳务合同", "低风险", "已到期"],
        "key_clauses": ["服务范围: 法律咨询", "付款: 按月结算"],
    },
    {
        "code": "CT-2026-0021",
        "name": "采购合同-设备供应商D",
        "contract_type": "purchase",
        "party_a": "益慧科技有限公司",
        "party_b": "设备供应商D",
        "amount": 8500000,
        "sign_date": date(2026, 1, 5),
        "effective_date": date(2026, 2, 1),
        "expire_date": date(2027, 8, 20),
        "status": "active",
        "owner": "王法务",
        "risk_level": "high",
        "tags": ["采购合同", "高风险", "金额>100万"],
        "key_clauses": ["质保期: 24个月", "违约金: 合同总额5%"],
    },
    {
        "code": "CT-2026-0010",
        "name": "框架合作协议-E公司",
        "contract_type": "other",
        "party_a": "益慧科技有限公司",
        "party_b": "E集团公司",
        "amount": 15000000,
        "sign_date": date(2025, 3, 1),
        "effective_date": date(2025, 3, 1),
        "expire_date": date(2026, 2, 28),
        "status": "archived",
        "owner": "张业务",
        "risk_level": "medium",
        "tags": ["框架合作", "已归档", "金额>100万"],
        "key_clauses": ["合作范围: 战略协同", "排他性: 无"],
    },
]

DEFAULT_CONTENT = """采购合同

甲方：益慧科技有限公司
乙方：{party_b}
签订日期：{sign_date}

第一条 合同标的
甲乙双方经友好协商，就甲方采购乙方产品事宜达成如下协议。

第二条 合同金额
合同总金额为人民币{amount}元。

第三条 付款方式
1. 合同签订后7个工作日内，甲方向乙方支付合同总额的30%；
2. 验收合格后支付60%；
3. 质保期满支付10%。

第四条 违约责任
任何一方违约需向对方支付合同总额5%的违约金；逾期交货每日按合同总额0.5‰支付违约金。

第五条 保密条款
双方均应对本合同内容承担保密义务，保密期限为合同终止后3年。

第八条 合同期限与续签
本合同有效期自生效日起至到期日止。合同期满前30日，如双方均无书面提出异议，本合同自动续签一年。

第十二条 争议解决
因本合同引起的争议，提交XX仲裁委员会仲裁。
"""

# 旧演示数据标记：历史上所有合同共用同一份 v1.0/v1.1 片段，导致对比结果恒为 3 处
LEGACY_VERSION_V10_MARKER = "第5条 付款方式"

_DRAFT_SUBSTITUTIONS = [
    ("合同签订后7个工作日内", "合同签订后30日内"),
    ("合同生效后5个工作日内", "合同生效后10个工作日内"),
    ("每日按合同总额0.5‰", "每日按合同总额0.3‰"),
    ("千分之五", "千分之三"),
]

_LEGAL_REVIEW_SUBSTITUTIONS = [
    ("合同签订后30日内", "收到乙方发票后15个工作日内"),
    ("合同签订后7个工作日内", "收到乙方发票后15个工作日内"),
    ("合同生效后10个工作日内", "合同生效后5个工作日内"),
    (
        "合同到期前30日，如双方均无书面提出异议，本合同自动续签一年。",
        "合同到期前90日，双方应协商续签事宜。",
    ),
    ("每日按合同总额0.3‰", "每日按合同总额0.5‰"),
    ("千分之三", "千分之五"),
]


def build_draft_version(final_content: str) -> str:
    """从终版正文生成业务草稿版（v1.0）。"""
    out = final_content
    for src, dst in _DRAFT_SUBSTITUTIONS:
        out = out.replace(src, dst)
    return out


def build_legal_review_version(final_content: str) -> str:
    """从终版正文生成法务审核版（v1.1）。"""
    out = build_draft_version(final_content)
    for src, dst in _LEGAL_REVIEW_SUBSTITUTIONS:
        out = out.replace(src, dst)
    return out


async def seed_cms_data(db: AsyncSession, user_id: int = 1) -> None:
    result = await db.execute(select(func.count()).select_from(ManagedContract))
    if result.scalar_one():
        return

    for item in SEED_CONTRACTS:
        content = DEFAULT_CONTENT.format(
            party_b=item["party_b"],
            sign_date=str(item.get("sign_date") or ""),
            amount=f"{item['amount']:,.0f}",
        )
        summary = f"{item['name']}，金额{item['amount']/10000:.0f}万元，{STATUS_LABELS.get(item['status'], item['status'])}。"
        contract = ManagedContract(
            user_id=user_id,
            code=item["code"],
            name=item["name"],
            contract_type=item["contract_type"],
            party_a=item["party_a"],
            party_b=item["party_b"],
            amount=item["amount"],
            sign_date=item.get("sign_date"),
            effective_date=item.get("effective_date"),
            expire_date=item.get("expire_date"),
            status=item["status"],
            owner=item["owner"],
            risk_level=item["risk_level"],
            tags_json=json.dumps(item["tags"], ensure_ascii=False),
            key_clauses_json=json.dumps(item["key_clauses"], ensure_ascii=False),
            ai_summary=summary,
            content_text=content,
        )
        db.add(contract)
        await db.flush()

        versions = [
            ContractVersion(
                contract_id=contract.id,
                version="v1.0",
                label="原始版 - 业务部门提供",
                content=build_draft_version(content),
                is_current=False,
                created_by="张业务",
            ),
            ContractVersion(
                contract_id=contract.id,
                version="v1.1",
                label="法务审核版",
                content=build_legal_review_version(content),
                is_current=False,
                created_by="王法务",
            ),
            ContractVersion(
                contract_id=contract.id,
                version="v2.1",
                label="终版 - 双方已签署",
                content=content,
                is_current=True,
                created_by="王法务",
            ),
        ]
        db.add_all(versions)

    await db.commit()


async def refresh_legacy_version_snapshots(db: AsyncSession) -> None:
    """将仍使用旧全局片段的 v1.0/v1.1 更新为基于各合同终版正文生成的版本。"""
    result = await db.execute(
        select(ContractVersion).where(ContractVersion.version.in_(["v1.0", "v1.1"]))
    )
    legacy_versions = list(result.scalars().all())
    if not legacy_versions:
        return

    contract_ids = {v.contract_id for v in legacy_versions}
    current_by_contract: dict[int, str] = {}
    for contract_id in contract_ids:
        cur_result = await db.execute(
            select(ContractVersion)
            .where(
                ContractVersion.contract_id == contract_id,
                ContractVersion.is_current.is_(True),
            )
            .limit(1)
        )
        current = cur_result.scalar_one_or_none()
        if current and (current.content or "").strip():
            current_by_contract[contract_id] = current.content

    updated = False
    for version in legacy_versions:
        base = current_by_contract.get(version.contract_id, "")
        if not base:
            continue
        raw = (version.content or "").strip()
        if not raw.startswith(LEGACY_VERSION_V10_MARKER):
            continue
        if version.version == "v1.0":
            version.content = build_draft_version(base)
            updated = True
        elif version.version == "v1.1":
            version.content = build_legal_review_version(base)
            updated = True

    if updated:
        await db.commit()


def _generate_code() -> str:
    return f"CT-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"


def _tags_from_json(raw: str) -> list[str]:
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []


async def get_stats(db: AsyncSession, user_id: int, user=None) -> dict:
    from app.core.access import contract_scope_filter

    today = date.today()
    soon = today + timedelta(days=30)
    base = select(ManagedContract)
    if user is not None:
        base = contract_scope_filter(base, user)
    else:
        base = base.where(ManagedContract.user_id == user_id)
    scoped_ids = select(base.subquery().c.id)

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    active = await db.scalar(
        select(func.count()).where(ManagedContract.id.in_(scoped_ids), ManagedContract.status == "active")
    )
    pending = await db.scalar(
        select(func.count()).where(ManagedContract.id.in_(scoped_ids), ManagedContract.status == "pending_sign")
    )
    archived = await db.scalar(
        select(func.count()).where(ManagedContract.id.in_(scoped_ids), ManagedContract.status == "archived")
    )
    expired = await db.scalar(
        select(func.count()).where(ManagedContract.id.in_(scoped_ids), ManagedContract.status == "expired")
    )
    expiring = await db.scalar(
        select(func.count()).where(
            ManagedContract.id.in_(scoped_ids),
            ManagedContract.status == "active",
            ManagedContract.expire_date.is_not(None),
            ManagedContract.expire_date <= soon,
            ManagedContract.expire_date >= today,
        )
    )
    high_risk = await db.scalar(
        select(func.count()).where(ManagedContract.id.in_(scoped_ids), ManagedContract.risk_level == "high")
    )
    return {
        "total": total or 0,
        "active": active or 0,
        "expiring_soon": expiring or 0,
        "expired": expired or 0,
        "pending_sign": pending or 0,
        "archived": archived or 0,
        "high_risk": high_risk or 0,
    }


async def list_contracts(
    db: AsyncSession,
    user_id: int,
    *,
    q: str = "",
    status: str | None = None,
    contract_type: str | None = None,
    risk_level: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user=None,
) -> tuple[list[ManagedContract], int]:
    query = select(ManagedContract)
    if user is not None:
        from app.core.access import contract_scope_filter

        query = contract_scope_filter(query, user)
    else:
        query = query.where(ManagedContract.user_id == user_id)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                ManagedContract.name.ilike(like),
                ManagedContract.code.ilike(like),
                ManagedContract.party_b.ilike(like),
                ManagedContract.tags_json.ilike(like),
            )
        )
    if status:
        query = query.where(ManagedContract.status == status)
    if contract_type:
        query = query.where(ManagedContract.contract_type == contract_type)
    if risk_level:
        query = query.where(ManagedContract.risk_level == risk_level)

    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0
    query = query.order_by(ManagedContract.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


def _infer_tag_levels(contract_type: str, tags: list[str], text: str) -> tuple[str, str, list[str]]:
    ctype = (contract_type or "").lower()
    level1 = "通用合同"
    level2 = ""
    if any(k in ctype for k in ("采购", "purchase")):
        level1 = "采购合同"
        level2 = "服务采购"
        if any(k in text for k in ("软件", "SaaS", "系统")):
            level2 = "软件采购"
        elif any(k in text for k in ("硬件", "设备")):
            level2 = "硬件采购"
        elif any(k in text for k in ("云", "算力")):
            level2 = "云服务采购"
    elif any(k in ctype for k in ("销售", "sale")):
        level1 = "销售合同"
        level2 = "服务销售"
    elif any(k in ctype for k in ("保密", "nda")):
        level1 = "通用合同"
        level2 = "保密协议"
    smart = list(tags or [])
    for kw, label in (
        ("SaaS", "SaaS"),
        ("框架", "年度框架"),
        ("里程碑", "按里程碑付款"),
        ("源代码", "源代码交付"),
        ("对赌", "对赌条款"),
        ("保密", "保密义务"),
    ):
        if kw in text and label not in smart:
            smart.append(label)
    if level1 and level1 not in smart:
        smart.insert(0, level1)
    if level2 and level2 not in smart:
        smart.insert(1, level2)
    return level1, level2, smart[:12]


async def create_contract(db: AsyncSession, user_id: int, data: dict) -> ManagedContract:
    text = data.get("content_text", "") or ""
    tags = list(data.get("tags", []))
    level1, level2, smart = _infer_tag_levels(data.get("contract_type", "purchase"), tags, text)
    contract = ManagedContract(
        user_id=user_id,
        department_id=data.get("department_id"),
        code=data.get("code") or _generate_code(),
        name=data["name"],
        contract_type=data.get("contract_type", "purchase"),
        party_a=data.get("party_a", "益慧科技有限公司"),
        party_b=data.get("party_b", ""),
        amount=data.get("amount", 0),
        currency=data.get("currency", "CNY"),
        sign_date=data.get("sign_date"),
        effective_date=data.get("effective_date"),
        expire_date=data.get("expire_date"),
        status=data.get("status", "pending_sign"),
        owner=data.get("owner", ""),
        tags_json=json.dumps(smart, ensure_ascii=False),
        tag_level1=data.get("tag_level1") or level1,
        tag_level2=data.get("tag_level2") or level2,
        content_text=text,
        ai_summary="",
        summary_locked=False,
        parse_status="done",
        risk_level="low",
    )
    if len(text) > 200:
        contract.ai_summary = "\n".join(_build_detail_summary(contract))
    else:
        contract.ai_summary = _build_short_summary_line(contract)
    db.add(contract)
    await db.flush()
    db.add(
        ContractVersion(
            contract_id=contract.id,
            version="v1.0",
            label="初始版本",
            content=contract.content_text or "（待补充合同正文）",
            is_current=True,
            created_by=contract.owner or "系统",
        )
    )
    await db.commit()
    await db.refresh(contract)
    from app.services import index_service

    await index_service.index_contract(db, contract)
    return contract


async def search_contracts(
    db: AsyncSession,
    user_id: int,
    q: str,
    mode: str = "hybrid",
    filters: list[dict] | None = None,
    limit: int = 50,
    user=None,
) -> dict:
    from app.services import search_service

    return await search_service.multi_modal_search(
        db,
        user_id,
        q=q,
        mode=mode,
        filters=filters,
        limit=limit,
        user=user,
    )


async def tag_cloud(db: AsyncSession, user_id: int, user=None) -> list[dict]:
    from app.core.access import contract_scope_filter

    query = select(ManagedContract.tags_json)
    if user is not None:
        query = contract_scope_filter(query, user)
    else:
        query = query.where(ManagedContract.user_id == user_id)
    result = await db.execute(query)
    counter: dict[str, int] = {}
    for (raw,) in result.all():
        for tag in _tags_from_json(raw):
            counter[tag] = counter.get(tag, 0) + 1
    return sorted([{"name": k, "count": v} for k, v in counter.items()], key=lambda x: -x["count"])


def _clean_clause(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def _first_match(text: str, patterns: list[str], group: int = 1) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                return m.group(0).strip()
    return None


def _parse_amount_from_text(text: str, fallback: float = 0) -> float | None:
    for pat in [
        r"(?:服务费用|合同总?金额)[^。\n]{0,50}人民币[【\[]?([\d,，]+)[】\]]?元",
        r"含税总价\s*\|\s*([\d,，]+)",
        r"每百万token\s*\d+元\s*\|\s*([\d,，]+)",
    ]:
        m = re.search(pat, text)
        if m:
            raw = m.group(1).replace(",", "").replace("，", "").strip()
            try:
                val = float(raw)
                if val > 0:
                    return val
            except ValueError:
                continue
    return fallback if fallback >= 10000 else None


def _build_short_summary_line(contract: ManagedContract) -> str:
    text = contract.content_text or ""
    amount = _parse_amount_from_text(text, contract.amount) or contract.amount
    type_label = TYPE_LABELS.get(contract.contract_type, "合同")
    status_label = STATUS_LABELS.get(contract.status, contract.status)
    parts = [f"《{contract.name}》为{type_label}，{status_label}"]
    if amount and amount >= 10000:
        parts.append(f"金额约{amount / 10000:.0f}万元")
    elif amount:
        parts.append(f"金额{amount:,.0f}元")
    if contract.party_a and contract.party_b:
        parts.append(f"甲方{contract.party_a}、乙方{contract.party_b}")
    period = re.search(
        r"(\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日[—\-](\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日",
        text,
    )
    if period:
        parts.append(
            f"服务期{period.group(1)}-{int(period.group(2)):02d}-{int(period.group(3)):02d}"
            f"至{period.group(4)}-{int(period.group(5)):02d}-{int(period.group(6)):02d}"
        )
    return "，".join(parts) + "。"


def _build_detail_summary(contract: ManagedContract) -> list[str]:
    text = contract.content_text or ""
    items: list[str] = []

    type_label = TYPE_LABELS.get(contract.contract_type, "合同")
    status_label = STATUS_LABELS.get(contract.status, contract.status)
    items.append(f"本合同为《{contract.name}》（{type_label}），当前状态为{status_label}。")

    if contract.party_a or contract.party_b:
        items.append(f"合同主体：甲方为{contract.party_a or '—'}，乙方为{contract.party_b or '—'}。")

    bg = _first_match(text, [r"鉴于[：:]\s*(.+?)(?=\n定义|\n服务范围|\n第一条|\n[^，。\n]{2,10}\n)"])
    if bg:
        items.append(f"签约背景：{_clean_clause(bg, 220)}")

    amount = _parse_amount_from_text(text, contract.amount)
    if amount and amount > 0:
        tax = "（含税，税率6%）" if "税率" in text and "6%" in text else "（含税）"
        items.append(f"合同金额：人民币{amount:,.0f}元{tax}。")

    scope = _first_match(
        text,
        [
            r"服务范围\s*\n(.+?)(?=\n乙方保证|\n服务内容|\n费用)",
            r"服务内容\s*\n(.+?)(?=\n费用|第四条|\n费用及支付)",
        ],
    )
    if scope:
        items.append(f"服务范围：{_clean_clause(scope, 240)}")

    service_lines: list[str] = []
    for label, pattern in [
        ("模型部署与托管", r"模型部署与托管[：:]([^。\n]+)"),
        ("推理服务", r"推理服务提供[：:]([^。\n]+)"),
        ("智能体开发", r"智能体开发部署与托管[：:]([^。\n]+)"),
        ("数据工程", r"数据工程服务[：:]([^。\n]+)"),
        ("技术支持", r"技术支持与平台响应[：:]([^。\n]+)"),
    ]:
        m = re.search(pattern, text)
        if m:
            service_lines.append(f"{label}：{_clean_clause(m.group(1), 100)}")
    if service_lines:
        items.append("核心服务内容：" + "；".join(service_lines) + "。")

    storage = _first_match(text, [r"数据存储容量不超过[【\[]?(\d+)[】\]]?T"])
    if storage:
        items.append(f"数据存储：平台数据存储容量上限为{storage}TB。")

    billing_parts: list[str] = []
    token_m = re.search(r"每套包含\s*(\d+)\s*亿Token", text)
    if token_m:
        billing_parts.append(f"每套含{token_m.group(1)}亿Token")
    period_m = re.search(
        r"(\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日[—\-](\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日",
        text,
    )
    if period_m:
        billing_parts.append(
            f"服务期限{period_m.group(1)}-{int(period_m.group(2)):02d}-{int(period_m.group(3)):02d}"
            f"至{period_m.group(4)}-{int(period_m.group(5)):02d}-{int(period_m.group(6)):02d}"
        )
    billing = _first_match(text, [r"计费方式[：:](.+?)(?=\n超量|。\n)"])
    if billing:
        billing_parts.append(_clean_clause(billing, 130))
    overuse = _first_match(text, [r"超量使用费[：:](.+?)。"])
    if overuse:
        billing_parts.append(f"超量计费：{_clean_clause(overuse, 100)}")
    if billing_parts:
        items.append("计费与服务期限：" + "；".join(billing_parts) + "。")

    pay = _first_match(text, [r"支付[：:](.+?)(?=\n甲方以银行|。\n|$)"])
    if pay:
        items.append(f"付款安排：{_clean_clause(pay, 160)}。")

    delivery = _first_match(text, [r"交付[：:](.+?)。"])
    if delivery:
        items.append(f"交付节点：{_clean_clause(delivery, 140)}。")

    if "使用许可" in text:
        lic = _first_match(text, [r"乙方授予甲方[^。]+。"])
        if lic:
            items.append(f"使用许可：{_clean_clause(lic, 160)}")
        restrict = _first_match(text, [r"甲方不得[^。]+。"])
        if restrict:
            items.append(f"使用限制：{_clean_clause(restrict, 160)}")

    if "用户数据" in text:
        items.append(
            "数据归属与安全：甲方对用户数据享有所有权；乙方仅在服务必要范围内处理数据，"
            "应采取不低于行业标准的安全措施，合同终止后30日内返还或删除数据。"
        )
    if "保密" in text:
        breach_conf = _first_match(text, [r"接收方违反本条[^。]+。"])
        if breach_conf:
            items.append(f"保密义务：双方对合同及商业秘密承担保密义务；{_clean_clause(breach_conf, 120)}")
        else:
            items.append("保密义务：双方对合同内容及商业秘密承担保密义务，违约方应赔偿全部损失。")
    if "知识产权" in text:
        ip = _first_match(text, [r"背景知识产权[^。]+。"])
        if ip:
            items.append(f"知识产权：{_clean_clause(ip, 160)}")
        output_ip = _first_match(text, [r"甲方利用乙方资源产生的数据及成果的知识产权[^。]+。"])
        if output_ip:
            items.append(f"成果归属：{_clean_clause(output_ip, 160)}")

    breach_parts: list[str] = []
    for pat in [
        r"数据安全、个人信息保护或保密义务[^。]+。",
        r"逾期支付服务费用[^。]+。",
        r"赔偿责任[^。]+最高限额[^。]+。",
        r"甲方无正当理由逾期支付[^。]+。",
    ]:
        m = re.search(pat, text)
        if m:
            breach_parts.append(_clean_clause(m.group(0), 110))
    if breach_parts:
        items.append("违约责任要点：" + "；".join(breach_parts) + "。")

    term = _first_match(text, [r"确需解除的[^。]+。"])
    if term:
        items.append(f"解除与终止：{_clean_clause(term, 140)}")

    dispute = _first_match(text, [r"因本合同[^。]*争议[^。]+仲裁[^。]+。"])
    if dispute:
        items.append(f"争议解决：{_clean_clause(dispute, 160)}")
    elif "仲裁" in text:
        items.append("争议解决：协商不成提交仲裁（详见合同争议解决条款）。")

    if contract.sign_date:
        items.append(f"签署日期：{contract.sign_date}。")
    else:
        sign_m = re.search(r"于(\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日订立", text)
        if sign_m:
            items.append(
                f"签订日期：{sign_m.group(1)}-{int(sign_m.group(2)):02d}-{int(sign_m.group(3)):02d}。"
            )

    if len(items) <= 2:
        clauses = json.loads(contract.key_clauses_json or "[]")
        if clauses:
            items.extend(clauses)
        elif text.strip():
            items.append(f"合同要点：{_clean_clause(text[:320], 300)}")
        elif contract.ai_summary and not contract.ai_summary.startswith("新建合同"):
            items.append(contract.ai_summary)

    return items


def _build_risk_summary(contract: ManagedContract) -> list[str]:
    text = contract.content_text or ""
    items: list[str] = []
    if re.search(r"千分之五|0\.5‰", text):
        items.append("逾期付款违约金较高（每日应付未付款项千分之五）")
    if re.search(r"总金额20%的违约金|合同总金额20%", text):
        items.append("数据安全/保密违约违约金高达合同总额20%")
    if re.search(r"最高限额不得超过[^。]{0,40}30%", text):
        items.append("乙方赔偿责任上限为已收金额的30%，甲方需关注责任限制条款")
    if re.search(r"不予退还", text):
        items.append("甲方违约或无故解约时，已支付款项可能不予退还")
    if re.search(r"超量使用|超量费用", text):
        items.append("Token等服务存在超量计费，需持续监控用量避免额外成本")
    if re.search(r"自动续签|自动续", text):
        items.append("含自动续签条款，到期前需主动提出异议")
    if re.search(r"单方解除|提前30日", text):
        items.append("解除合同需提前30日书面通知，并承担已发生服务费用")
    if contract.risk_level == "high":
        items.extend(["整体风险等级偏高", "建议重点复核违约金与付款条款"])
    if not items:
        if contract.risk_level == "high":
            return ["违约金比例较高(每日0.5‰，年化18.25%)", "付款条件变更风险", "自动续签条款需关注"]
        return ["整体风险可控", "建议定期复核关键条款"]
    return items


def _extract_dates_from_text(text: str) -> list[str]:
    items: list[str] = []
    for m in re.finditer(r"(\d{4})年[【\[](\d{1,2})[】\]](?:月[【\[](\d{1,2})[】\]])?", text):
        y, mo, d = m.group(1), int(m.group(2)), m.group(3)
        label = text[max(0, m.start() - 20) : m.start()]
        if d:
            date_str = f"{y}-{mo:02d}-{int(d):02d}"
        else:
            date_str = f"{y}-{mo:02d}"
        if any(k in label for k in ("订立", "签订", "签署")):
            items.append(f"{date_str} 合同签订")
        elif any(k in label for k in ("开放", "交付")):
            items.append(f"{date_str} 服务开放/交付")
    period_m = re.search(
        r"(\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日[—\-](\d{4})年[【\[](\d+)[】\]]月[【\[](\d+)[】\]]日",
        text,
    )
    if period_m:
        start = f"{period_m.group(1)}-{int(period_m.group(2)):02d}-{int(period_m.group(3)):02d}"
        end = f"{period_m.group(4)}-{int(period_m.group(5)):02d}-{int(period_m.group(6)):02d}"
        items.append(f"{start} 服务期开始")
        items.append(f"{end} 服务期届满")
    pay = _first_match(text, [r"合同生效后(\d+)个工作日内[^。]+开具[^。]+。"])
    if pay:
        items.append(f"合同生效后 开票及付款流程启动（详见付款条款）")
    return items


def _build_timeline_summary(contract: ManagedContract) -> list[str]:
    items: list[str] = []
    if contract.sign_date:
        items.append(f"{contract.sign_date} 合同签署")
    if contract.effective_date:
        items.append(f"{contract.effective_date} 合同生效")
    for entry in _extract_dates_from_text(contract.content_text or ""):
        if entry not in items:
            items.append(entry)
    if contract.expire_date:
        end_line = f"{contract.expire_date} 合同到期"
        if end_line not in items:
            items.append(end_line)
    return items or ["暂无时间节点"]


def build_summary(contract: ManagedContract, summary_type: str) -> list[str]:
    if summary_type == "risk":
        return _build_risk_summary(contract)
    if summary_type == "timeline":
        return _build_timeline_summary(contract)
    if summary_type == "detail":
        return _build_detail_summary(contract)
    clauses = json.loads(contract.key_clauses_json or "[]")
    if clauses:
        return clauses
    if contract.content_text and contract.content_text.strip():
        return _build_detail_summary(contract)[:5]
    return [
        f"合同金额: {contract.amount:,.0f} {contract.currency}",
        f"合同期限: {contract.effective_date} - {contract.expire_date}",
        f"状态: {STATUS_LABELS.get(contract.status, contract.status)}",
    ]


async def build_summary_async(contract: ManagedContract, summary_type: str) -> list[str]:
    # 人工锁定后，详情摘要直接使用已保存终版
    if summary_type == "detail" and getattr(contract, "summary_locked", False) and (contract.ai_summary or "").strip():
        lines = [ln.strip() for ln in contract.ai_summary.splitlines() if ln.strip()]
        return lines or [contract.ai_summary]
    if summary_type == "detail" and (contract.content_text or "").strip():
        from app.services.llm_service import generate_contract_detail_summary

        llm_items = await generate_contract_detail_summary(
            contract.name,
            contract.content_text or "",
            {
                "party_a": contract.party_a,
                "party_b": contract.party_b,
                "amount": contract.amount,
                "status": contract.status,
                "contract_type": contract.contract_type,
            },
        )
        if llm_items:
            return llm_items
    return build_summary(contract, summary_type)


QA_ANSWERS = {
    "违约金": "根据合同第12.3条，逾期交货每日按合同总额的0.5‰支付违约金，违约金总额不超过合同总额的5%。",
    "到期": "合同到期日前30日如双方均未提出异议，自动续签一年。",
    "续签": "合同可以自动续签，条件是双方在到期前30日内均未提出异议（参见第8.2条）。",
    "付款": "付款方式为：签约后付30%，验收合格后付60%，质保期满付10%。",
    "保密": "根据保密条款，双方均有保密义务，保密期限为合同终止后3年。",
    "争议": "争议解决方式为提交XX仲裁委员会仲裁。",
    "风险": "主要风险包括：违约金比例较高、付款条件对现金流有压力、自动续签条款需关注。",
}

_QA_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "金额": ["金额", "合同金额", "多少钱", "总价", "服务费用", "费用", "人民币", "含税", "token", "Token"],
    "付款": ["付款", "支付", "发票", "结算", "预付款"],
    "违约金": ["违约金", "违约"],
    "到期": ["到期", "期限", "届满", "有效期"],
    "续签": ["续签", "自动续"],
    "保密": ["保密"],
    "争议": ["争议", "仲裁", "诉讼"],
    "甲方": ["甲方"],
    "乙方": ["乙方"],
}


def _question_topics(question: str) -> list[str]:
    q = question.strip()
    topics: list[str] = []
    for topic, terms in _QA_TOPIC_KEYWORDS.items():
        if any(term.lower() in q.lower() for term in terms):
            topics.append(topic)
    return topics


def _find_relevant_excerpt(text: str, keywords: list[str], limit: int = 220) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if any(kw in line for kw in keywords):
            block = "\n".join(lines[i : i + 3]).strip()
            return _clean_clause(block, limit)
    return ""


def answer_from_contract_knowledge(
    contract: ManagedContract,
    question: str,
    chunks: list | None = None,
) -> dict | None:
    """Rule-based contract Q&A from structured fields and indexed chunks."""
    topics = _question_topics(question)
    if not topics:
        return None

    text = contract.content_text or ""
    chunk_text = "\n".join(getattr(ch, "content", "") for ch in (chunks or []))
    corpus = f"{text}\n{chunk_text}"
    answer_parts: list[str] = []
    citations: list[str] = []
    details: list[dict] = []

    if "金额" in topics:
        amount = _parse_amount_from_text(corpus, contract.amount)
        excerpt = _find_relevant_excerpt(
            corpus,
            ["服务费用", "合同金额", "含税总价", "费用及支付", "人民币", "Token"],
        )
        if amount and amount > 0:
            answer_parts.append(
                f"《{contract.name}》合同金额约为人民币 {amount:,.0f} 元（含税）。"
            )
        elif re.search(r"服务费用共计人民币[【\[]?[】\]]?元", corpus):
            answer_parts.append(
                f"《{contract.name}》正文费用条款中金额待填写，但附件服务清单列明具体报价，请查阅「费用及支付」及附件一。"
            )
        elif contract.amount and contract.amount > 0:
            answer_parts.append(
                f"《{contract.name}》登记金额为人民币 {contract.amount:,.0f} 元。"
            )
        if excerpt:
            answer_parts.append(f"相关条款：{excerpt}")
            citations.append("费用及支付")
            details.append({"section": "费用及支付", "excerpt": excerpt, "chunk_id": None})

    if "付款" in topics and "付款" not in " ".join(answer_parts):
        excerpt = _find_relevant_excerpt(corpus, ["付款", "支付", "发票", "结算"])
        if excerpt:
            answer_parts.append(f"付款安排：{excerpt}")
            citations.append("付款条款")
            details.append({"section": "付款条款", "excerpt": excerpt, "chunk_id": None})
        elif "付款" in QA_ANSWERS:
            answer_parts.append(QA_ANSWERS["付款"])
            citations.append("付款相关条款")

    for topic in ("违约金", "到期", "续签", "保密", "争议"):
        if topic in topics and topic in QA_ANSWERS:
            excerpt = _find_relevant_excerpt(
                corpus,
                _QA_TOPIC_KEYWORDS.get(topic, [topic]),
            )
            answer_parts.append(excerpt or QA_ANSWERS[topic])
            citations.append(f"{topic}相关条款")
            if excerpt:
                details.append({"section": f"{topic}相关条款", "excerpt": excerpt, "chunk_id": None})

    if "甲方" in topics and contract.party_a:
        answer_parts.append(f"甲方为 {contract.party_a}。")
        citations.append("合同主体")
    if "乙方" in topics and contract.party_b:
        answer_parts.append(f"乙方为 {contract.party_b}。")
        citations.append("合同主体")

    if chunks and not details:
        for ch in chunks[:2]:
            title = getattr(ch, "section_title", None) or f"片段{getattr(ch, 'chunk_index', 0) + 1}"
            excerpt = _clean_clause(getattr(ch, "content", ""), 200)
            details.append(
                {
                    "section": title,
                    "excerpt": excerpt,
                    "chunk_id": getattr(ch, "id", None),
                }
            )
            citations.append(title)

    if not answer_parts:
        return None

    confidence = "medium"
    if "金额" in topics:
        amt = _parse_amount_from_text(corpus, contract.amount)
        if amt and amt > 0:
            confidence = "high"

    return {
        "answer": " ".join(answer_parts),
        "citations": list(dict.fromkeys(citations)) or ["合同正文"],
        "citation_details": details,
        "confidence": confidence,
    }


def _keyword_qa_fallback(contract: ManagedContract, question: str) -> dict:
    structured = answer_from_contract_knowledge(contract, question)
    if structured:
        return structured

    answer_parts = []
    citations = []
    for key, val in QA_ANSWERS.items():
        if key in question:
            answer_parts.append(val)
            citations.append(f"{key}相关条款")
    if not answer_parts:
        answer_parts.append(
            f"关于「{question}」，需结合《{contract.name}》正文进一步分析。"
            "根据现有条款，建议重点查阅付款、违约责任和续签相关章节。"
        )
        citations.append("合同正文")
    return {
        "answer": " ".join(answer_parts),
        "citations": citations,
        "citation_details": [],
        "confidence": "medium",
    }


async def answer_contract_qa(db: AsyncSession, contract: ManagedContract, question: str) -> dict:
    from app.services import rag_service

    return await rag_service.answer_contract_question(db, contract, question)


async def compare_versions(
    db: AsyncSession,
    contract_id: int,
    left_id: int,
    right_id: int,
) -> dict:
    from app.services import compare_service

    return await compare_service.compare_versions(db, contract_id, left_id, right_id)


async def enqueue_import(db: AsyncSession, user_id: int, filename: str, file_path: str) -> ContractImportTask:
    task = ContractImportTask(
        user_id=user_id,
        filename=filename,
        file_path=file_path,
        status="queued",
        progress=0,
        retry_count=0,
        content_text="",
        parse_warnings_json="[]",
        confidence=0,
        extracted_json="{}",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_import_tasks(db: AsyncSession, user_id: int, *, limit: int = 50) -> list[ContractImportTask]:
    result = await db.execute(
        select(ContractImportTask)
        .where(ContractImportTask.user_id == user_id)
        .order_by(ContractImportTask.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def process_import(db: AsyncSession, user_id: int, filename: str, file_path: str) -> ContractImportTask:
    """Sync wrapper: enqueue then run job immediately (tests / fallback)."""
    task = await enqueue_import(db, user_id, filename, file_path)
    from app.services.import_queue import run_import_job

    await run_import_job(task.id)
    refreshed = await db.get(ContractImportTask, task.id)
    return refreshed or task


def _next_version_number(versions: list[ContractVersion]) -> str:
    best = (1, 0)
    for v in versions:
        m = re.match(r"v(\d+)\.(\d+)", v.version or "")
        if m:
            pair = (int(m.group(1)), int(m.group(2)))
            if pair > best:
                best = pair
    return f"v{best[0]}.{best[1] + 1}"


def _normalize_party(value: str) -> str:
    text = (value or "").strip().lower()
    for ch in " \t\n\r　·•":
        text = text.replace(ch, "")
    return text


def _party_field_match(extracted: str, ledger: str) -> bool:
    left = _normalize_party(extracted)
    right = _normalize_party(ledger)
    if not left:
        return True
    if not right:
        return False
    if left == right:
        return True
    return left in right or right in left


def _parties_match(extracted_a: str, extracted_b: str, ledger_a: str, ledger_b: str) -> bool:
    has_party = bool(_normalize_party(extracted_a) or _normalize_party(extracted_b))
    if not has_party:
        return True
    direct = _party_field_match(extracted_a, ledger_a) and _party_field_match(extracted_b, ledger_b)
    swapped = _party_field_match(extracted_a, ledger_b) and _party_field_match(extracted_b, ledger_a)
    return direct or swapped


def _name_similarity(left: str, right: str) -> float:
    a = (left or "").strip()
    b = (right or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return max(0.88, SequenceMatcher(None, a, b).ratio())
    return SequenceMatcher(None, a, b).ratio()


def _build_link_match_reason(name_sim: float, parties_ok: bool, has_party: bool) -> str:
    parts: list[str] = []
    if name_sim >= 0.88:
        parts.append("名称高度相似")
    elif name_sim >= 0.55:
        parts.append("名称相似")
    else:
        parts.append("名称部分相似")
    if has_party and parties_ok:
        parts.append("甲乙双方一致")
    return " · ".join(parts)


async def suggest_import_link_contracts(
    db: AsyncSession,
    user_id: int,
    *,
    name: str = "",
    party_a: str = "",
    party_b: str = "",
    q: str = "",
    limit: int = 10,
) -> list[dict]:
    result = await db.execute(
        select(ManagedContract)
        .where(ManagedContract.user_id == user_id)
        .order_by(ManagedContract.updated_at.desc())
    )
    contracts = list(result.scalars().all())
    keyword = (q or "").strip()
    has_party = bool(_normalize_party(party_a) or _normalize_party(party_b))
    has_name = bool((name or "").strip())
    scored: list[dict] = []

    for contract in contracts:
        if keyword:
            like = keyword.lower()
            haystack = " ".join(
                [contract.name, contract.code, contract.party_a, contract.party_b]
            ).lower()
            if like not in haystack:
                continue

        name_sim = _name_similarity(name, contract.name) if has_name else 0.0
        parties_ok = _parties_match(party_a, party_b, contract.party_a, contract.party_b)

        if keyword and not has_name and not has_party:
            match_score = 50
            match_reason = "关键词匹配"
        elif has_name and has_party:
            if not parties_ok or name_sim < 0.45:
                if keyword:
                    match_score = 40
                    match_reason = "关键词匹配"
                else:
                    continue
            else:
                match_score = int(min(99, name_sim * 70 + (30 if parties_ok else 0)))
                match_reason = _build_link_match_reason(name_sim, parties_ok, has_party)
        elif has_name:
            if name_sim < 0.45 and not keyword:
                continue
            match_score = int(min(99, name_sim * 100))
            match_reason = _build_link_match_reason(name_sim, parties_ok, has_party)
        elif has_party:
            if not parties_ok:
                if keyword:
                    match_score = 40
                    match_reason = "关键词匹配"
                else:
                    continue
            else:
                match_score = 75
                match_reason = "甲乙双方一致"
        else:
            if not keyword:
                continue
            match_score = 40
            match_reason = "关键词匹配"

        scored.append(
            {
                "contract": contract,
                "match_score": match_score,
                "match_reason": match_reason,
            }
        )

    scored.sort(key=lambda item: (-item["match_score"], -item["contract"].updated_at.timestamp()))
    return scored[:limit]


async def suggest_import_link_from_task(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    q: str = "",
    limit: int = 10,
) -> tuple[list[dict], dict]:
    task = await db.get(ContractImportTask, task_id)
    if not task or task.user_id != user_id:
        raise ValueError("导入任务不存在")
    data = json.loads(task.extracted_json or "{}")
    meta = {
        "extracted_name": str(data.get("name") or ""),
        "extracted_party_a": str(data.get("party_a") or ""),
        "extracted_party_b": str(data.get("party_b") or ""),
    }
    items = await suggest_import_link_contracts(
        db,
        user_id,
        name=meta["extracted_name"],
        party_a=meta["extracted_party_a"],
        party_b=meta["extracted_party_b"],
        q=q,
        limit=limit,
    )
    return items, meta


async def append_import_as_version(
    db: AsyncSession,
    user_id: int,
    contract_id: int,
    task: ContractImportTask,
    data: dict,
    content_text: str,
    version_label: str,
) -> tuple[ManagedContract, str]:
    contract = await db.get(ManagedContract, contract_id)
    if not contract or contract.user_id != user_id:
        raise ValueError("关联合同不存在")

    result = await db.execute(
        select(ContractVersion).where(ContractVersion.contract_id == contract.id)
    )
    versions = list(result.scalars().all())
    for v in versions:
        v.is_current = False

    new_version = _next_version_number(versions)
    label = version_label.strip() or f"导入版 - {task.filename}"
    db.add(
        ContractVersion(
            contract_id=contract.id,
            version=new_version,
            label=label,
            content=content_text,
            is_current=True,
            created_by=contract.owner or "导入",
        )
    )

    contract.content_text = content_text
    contract.index_status = "pending"
    if data.get("key_clauses"):
        contract.key_clauses_json = json.dumps(data["key_clauses"], ensure_ascii=False)

    tags = _tags_from_json(contract.tags_json)
    for tag in data.get("tags", []):
        if tag and tag not in tags:
            tags.append(tag)
    if "版本导入" not in tags:
        tags.append("版本导入")
    contract.tags_json = json.dumps(tags, ensure_ascii=False)

    await db.flush()
    from app.services import index_service

    await index_service.index_contract(db, contract)
    task.status = "confirmed"
    await db.commit()
    await db.refresh(contract)
    return contract, new_version


async def confirm_import(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    target_contract_id: int | None = None,
    version_label: str = "导入版本",
    department_id: int | None = None,
) -> tuple[ManagedContract, str, str | None]:
    """Returns (contract, import_mode, new_version_label)."""
    task = await db.get(ContractImportTask, task_id)
    if not task or task.user_id != user_id:
        raise ValueError("导入任务不存在")
    if task.status not in ("completed", "confirmed"):
        raise ValueError("任务尚未解析完成，请稍后再确认入库")
    data = json.loads(task.extracted_json or "{}")
    content_text = task.content_text or data.get("content_text", "")
    if not content_text:
        content_text = DEFAULT_CONTENT.format(
            party_b=data.get("party_b", ""),
            sign_date=data.get("sign_date", ""),
            amount=f"{data.get('amount', 0):,.0f}",
        )

    if target_contract_id:
        contract, new_version = await append_import_as_version(
            db, user_id, target_contract_id, task, data, content_text, version_label
        )
        return contract, "version", new_version

    contract = await create_contract(
        db,
        user_id,
        {
            "name": data.get("name", "导入合同"),
            "contract_type": data.get("contract_type", "purchase"),
            "party_a": data.get("party_a", ""),
            "party_b": data.get("party_b", ""),
            "amount": data.get("amount", 0),
            "sign_date": date.fromisoformat(data["sign_date"]) if data.get("sign_date") else None,
            "effective_date": date.fromisoformat(data["effective_date"]) if data.get("effective_date") else None,
            "expire_date": date.fromisoformat(data["expire_date"]) if data.get("expire_date") else None,
            "status": "pending_sign",
            "tags": data.get("tags", ["AI导入"]),
            "content_text": content_text,
            "department_id": department_id,
        },
    )
    task.status = "confirmed"
    await db.commit()
    return contract, "new", None
