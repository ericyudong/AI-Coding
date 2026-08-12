"""Role and permission definitions for α version PRD."""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    LEGAL = "legal"
    BUSINESS = "business"
    SALES = "sales"
    PROCUREMENT = "procurement"
    FINANCE = "finance"
    MANAGER = "manager"


ROLE_LABELS: dict[str, str] = {
    Role.SYSTEM_ADMIN: "系统管理员",
    Role.LEGAL: "法务人员",
    Role.BUSINESS: "业务人员",
    Role.SALES: "销售人员",
    Role.PROCUREMENT: "采购人员",
    Role.FINANCE: "财务人员",
    Role.MANAGER: "管理人员",
}

# Feature keys used for route/menu gating
FEATURE_WORKBENCH = "workbench"
FEATURE_KNOWLEDGE = "knowledge"
FEATURE_CONTRACT_IMPORT = "contract_import"
FEATURE_CONTRACT_SEARCH = "contract_search"
FEATURE_CONTRACT_DETAIL = "contract_detail"
FEATURE_CONTRACT_TAG_EDIT = "contract_tag_edit"
FEATURE_CONTRACT_SUMMARY_EDIT = "contract_summary_edit"
FEATURE_SUPPLIER = "supplier"
FEATURE_CUSTOMER = "customer"
FEATURE_PERFORMANCE = "performance"
FEATURE_PERFORMANCE_ALL = "performance_all"
FEATURE_SYSTEM_ADMIN = "system_admin"
FEATURE_EXPORT = "export"
FEATURE_BUSINESS_MODEL = "business_model"

# Role → allowed features (True = full access within data scope)
ROLE_FEATURES: dict[str, set[str]] = {
    Role.SYSTEM_ADMIN: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_IMPORT,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_CONTRACT_TAG_EDIT,
        FEATURE_CONTRACT_SUMMARY_EDIT,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_PERFORMANCE_ALL,
        FEATURE_SYSTEM_ADMIN,
        FEATURE_EXPORT,
        FEATURE_BUSINESS_MODEL,
    },
    Role.LEGAL: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_IMPORT,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_CONTRACT_TAG_EDIT,
        FEATURE_CONTRACT_SUMMARY_EDIT,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_PERFORMANCE_ALL,
        FEATURE_EXPORT,
    },
    Role.BUSINESS: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_CONTRACT_SUMMARY_EDIT,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
    },
    Role.SALES: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_CONTRACT_SUMMARY_EDIT,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_EXPORT,
    },
    Role.PROCUREMENT: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_CONTRACT_SUMMARY_EDIT,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_EXPORT,
    },
    Role.FINANCE: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_PERFORMANCE_ALL,
        FEATURE_EXPORT,
    },
    Role.MANAGER: {
        FEATURE_WORKBENCH,
        FEATURE_KNOWLEDGE,
        FEATURE_CONTRACT_SEARCH,
        FEATURE_CONTRACT_DETAIL,
        FEATURE_SUPPLIER,
        FEATURE_CUSTOMER,
        FEATURE_PERFORMANCE,
        FEATURE_PERFORMANCE_ALL,
        FEATURE_EXPORT,
        FEATURE_BUSINESS_MODEL,
    },
}

# Roles that can see all department / all performance data
CROSS_DEPT_ROLES = {Role.SYSTEM_ADMIN, Role.LEGAL, Role.FINANCE, Role.MANAGER}

RECOMMENDED_QUESTIONS: dict[str, list[str]] = {
    Role.SYSTEM_ADMIN: [
        "本月系统入库了多少份合同？",
        "哪些合同解析失败需要处理？",
        "履约预警有多少条未处理？",
    ],
    Role.LEGAL: [
        "公司以前签过类似的软件采购合同吗？",
        "我们通常如何约定知识产权归属？",
        "哪些合同履约节点即将逾期？",
    ],
    Role.BUSINESS: [
        "某客户的历史合作合同有哪些？",
        "同类项目通常如何约定付款条款？",
        "本部门近期到期的合同有哪些？",
    ],
    Role.SALES: [
        "哪家客户去年销售额最高？",
        "腾讯集团（含关联公司）一共产生多少交易？",
        "今年新增了哪些客户？",
    ],
    Role.PROCUREMENT: [
        "华为过去合作过哪些项目？",
        "哪家供应商延期交付最多？",
        "本月有哪些付款节点到期？",
    ],
    Role.FINANCE: [
        "本月到期应付款有哪些？",
        "合同金额按类型如何分布？",
        "哪些客户回款周期最长？",
    ],
    Role.MANAGER: [
        "本年度合同数量和金额趋势如何？",
        "企业整体履约健康度怎么样？",
        "Top 客户和供应商分别是谁？",
    ],
}


def has_feature(role: str | None, feature: str) -> bool:
    if not role:
        return False
    return feature in ROLE_FEATURES.get(role, set())


def can_access_all_data(role: str | None) -> bool:
    return role in CROSS_DEPT_ROLES


def recommended_questions(role: str | None) -> list[str]:
    if role and role in RECOMMENDED_QUESTIONS:
        return RECOMMENDED_QUESTIONS[role]
    return RECOMMENDED_QUESTIONS[Role.LEGAL]
