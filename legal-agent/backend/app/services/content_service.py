"""Home page and static content data."""
from app.schemas.schemas import AiModuleCard, NewsItem, QuickLink

AI_MODULES: list[AiModuleCard] = [
    AiModuleCard(
        id="knowledge",
        title="知识资产AI",
        subtitle="企业知识问答与知识库浏览",
        features=["企业知识问答", "合同库", "条款库", "引用溯源"],
        route="/knowledge",
    ),
    AiModuleCard(
        id="contract",
        title="合同AI",
        subtitle="合同导入、搜索、详情与摘要",
        features=["合同导入与解析", "企业合同搜索", "智能标签", "版本管理"],
        route="/cms",
    ),
    AiModuleCard(
        id="performance",
        title="履约AI",
        subtitle="履约管理与交易伙伴中心",
        features=["履约助手", "供应商中心", "客户中心", "到期预警"],
        route="/performance",
    ),
    AiModuleCard(
        id="business-model",
        title="商业模式AI",
        subtitle="商业经验沉淀与分析（预留）",
        features=["交易模式分析", "合作模式沉淀", "功能开发中"],
        route="/business-model",
    ),
]

QUICK_LINKS: list[QuickLink] = [
    QuickLink(id="contract-import", label="合同导入", icon="upload"),
    QuickLink(id="contract-search", label="合同搜索", icon="search"),
    QuickLink(id="performance", label="履约总览", icon="timeline"),
    QuickLink(id="suppliers", label="供应商中心", icon="supplier"),
    QuickLink(id="customers", label="客户中心", icon="customer"),
    QuickLink(id="knowledge", label="知识问答", icon="qa"),
    QuickLink(id="admin", label="系统管理", icon="admin"),
]

NEWS_ITEMS: list[NewsItem] = [
    NewsItem(id=1, title="国务院常务会议：部署进一步稳就业稳经济推动高质量发展", date="2026-06-12", category="express"),
    NewsItem(id=2, title="最高人民法院发布劳动争议典型案例", date="2026-06-10", category="express"),
    NewsItem(id=3, title="《数据安全法》实施三周年合规指引更新", date="2026-06-08", category="featured"),
    NewsItem(id=4, title="企业出海法律风险防控专题", date="2026-06-05", category="module"),
    NewsItem(id=5, title="新公司法配套司法解释实务解读", date="2026-06-01", category="featured"),
]

SEARCH_SUGGESTIONS = [
    "劳动合同到期后终止，是否需要提前一个月通知劳动者？",
    "违章建筑能否作为保险标的？",
    "刑事询问笔录是否都能作为民事案件认定事实的依据？",
    "未取得发票的支出可否凭借收款凭证追补至发生年度在企业所得税税前扣除？",
]

LABOR_EXAMPLES = [
    "员工试用期内工作表现不佳，用人单位可以解除劳动合同吗？",
    "北京最新最低工资标准是多少？",
    "北京与上海的医疗期分别如何计算？",
]

SEARCH_TYPES = [
    {"id": "comprehensive", "label": "综合分析"},
    {"id": "regulation", "label": "法规查询"},
    {"id": "case", "label": "类案检索"},
    {"id": "penalty", "label": "行政处罚"},
    {"id": "interpretation", "label": "专业解读"},
]

DRAFT_STYLES = ["简明居中", "详细严谨", "偏向甲方", "偏向乙方"]
