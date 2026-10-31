"""种子数据（一）：静态基础数据。

包含系统、编码器、算力、数据资产与切片、四层标签体系、模型基座与能力声明、
注册路径与里程碑风险、云边节点、合规台账、运营编制。
运行期数据（训练 / 推理 / 评测 / Agent 会话）见 `app/seed.py`。
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ROLE_DEFINITIONS, hash_password

# 演示账号口令。必须满足密码策略（长度/大小写/数字），否则改密接口自己就把演示账号拒了。
SEED_PASSWORDS = {
    "admin": "Admin@2026",
    "cmo": "Cmo@2026",
    "algo01": "Algo@2026",
    "doctor01": "Doctor@2026",
    "doctor02": "Doctor@2026",
    "algo02": "Algo@2026",
    "reg01": "Reg@2026",
    "ops01": "Ops@2026",
}
from app.models.agent import AgentCapability
from app.models.asset import AssetExtension, DataAsset, Slide, StorageStat
from app.models.compliance import (
    ChangeRegistration,
    ConsentRecord,
    EthicsRecord,
    ReviewQuestionAnswer,
    SecurityAssessment,
)
from app.models.edge import EdgeNode
from app.models.label import Annotation, AnnotatorProfile, Arbitration, LabelSchema, LabelSop, QcRecord
from app.models.modeling import ComputeResource, EncoderRegistry, ModelBase
from app.models.registry import ClinicalTrialSite
from app.models.system import Dictionary, RoleModel, SystemConfig, User
from app.services import ops_service, registry_service
from app.services.encoder_service import BUILTIN_ENCODERS
from app.services.wsi_service import open_slide

logger = logging.getLogger("seed")


def _log(message: str, *args) -> None:
    """同时走 logging 与 print，保证在任何重定向/管道环境下都能看到进度。"""
    text = message % args if args else message
    logger.info(text)
    print(text, flush=True)

SITES = [
    {"code": "SITE-A", "hospital": "院内主中心", "region": "本院", "role": "主中心"},
    {"code": "SITE-B", "hospital": "协作医院 B", "region": "同城三甲", "role": "协作中心"},
    {"code": "SITE-C", "hospital": "外部验证中心 C", "region": "异地三甲", "role": "外部验证中心"},
]
IN_DOMAIN_SITES = ["SITE-A", "SITE-B"]
EXTERNAL_SITE = "SITE-C"


# =============================================================== 系统
def seed_system(db: Session) -> None:
    for key, role in ROLE_DEFINITIONS.items():
        db.add(RoleModel(
            key=key, name=role["name"], description=role["description"],
            permissions_json=json.dumps(role["permissions"], ensure_ascii=False),
            is_builtin=True, sort_order=list(ROLE_DEFINITIONS).index(key),
        ))
    db.flush()

    roles = {r.key: r for r in db.query(RoleModel).all()}
    users = [
        ("admin", "系统管理员", "admin", "信息科", "平台管理员", "product"),
        ("cmo", "林主任", "cmo", "病理科", "主任医师 / 首席医学官", "product"),
        ("doctor01", "陈医师", "pathologist", "病理科", "副主任医师", "product"),
        ("doctor02", "吴医师", "pathologist", "病理科", "主治医师", "product"),
        ("algo01", "赵工", "algorithm", "算法部", "算法负责人", "research"),
        ("algo02", "孙工", "algorithm", "算法部", "编码器组负责人", "research"),
        ("reg01", "周经理", "compliance", "注册部", "注册与合规负责人", "product"),
        ("ops01", "郑主管", "operator", "运营部", "科室运营", "product"),
    ]
    for username, real_name, role_key, dept, title, env in users:
        # 机构与数据范围：admin 全院；cmo/doctor 覆盖多中心；其余演示账号限本中心，
        # 这样一登录就能在页头看到「我的数据范围」，也不会误以为全院数据都能看。
        org_code = "ORG-SH-01"
        site_code = {"admin": "", "cmo": "", "doctor01": "SITE-A",
                     "doctor02": "SITE-B", "algo01": ""}.get(username, "SITE-A")
        data_scope = {"admin": "all", "cmo": "org", "algo01": "org"}.get(username, "site")
        user = User(
            username=username,
            password_hash=hash_password(SEED_PASSWORDS.get(username, f"{username}123")),
            real_name=real_name, department=dept, title=title,
            employee_no=f"SH{abs(hash(username)) % 100000:05d}",
            email=f"{username}@smarthealth.local",
            deployment_env=env, is_active=True,
            org_code=org_code, site_code=site_code, data_scope=data_scope,
        )
        user.roles.append(roles[role_key])
        db.add(user)

    configs = [
        ("deployment_env", settings.deployment_env, "string", "security", "部署环境",
         "research=科研/探索线（允许非商用权重）；product=商用主线（仅允许可商用权重）"),
        ("agent.confidence_threshold", str(settings.agent_confidence_threshold), "float", "agent",
         "Agent 置信度阈值", "校准后置信度低于该值触发拒识并转人工复核"),
        ("agent.max_regions", str(settings.agent_max_regions), "int", "agent",
         "单切片探查区域上限", "对标业内分层探查方案平均约 47 个区域"),
        ("agent.trajectories", str(settings.agent_navigation_trajectories), "int", "agent",
         "诊断多轨迹投票条数", "不同区域子集下的独立结论，用于稳定性评估"),
        ("tile.size", str(settings.default_tile_size), "int", "pipeline",
         "图块尺寸(px)", "20X 层（mpp 0.5）的图块边长"),
        ("tile.min_tissue_ratio", "0.05", "float", "pipeline",
         "图块最低组织占比", "低于该值的图块视为背景并丢弃"),
        ("audit.chain_enabled", "true", "bool", "security", "审计哈希链",
         "关键动作全量写入 SHA-256 链式审计记录"),
        ("reject.manual_review", "true", "bool", "agent", "拒识转人工",
         "拒识结论必须生成医生终审工单"),
    ]
    for key, value, vtype, category, label, desc in configs:
        db.add(SystemConfig(key=key, value=value, value_type=vtype, category=category,
                            label=label, description=desc))

    dictionaries = [
        ("staining", "HE", "H&E", 1), ("staining", "IHC", "免疫组化", 2),
        ("staining", "SPECIAL", "特殊染色（巴氏）", 3),
        ("magnification", "40X", "40X（mpp≈0.25）", 1), ("magnification", "20X", "20X（mpp≈0.50）", 2),
        ("magnification", "10X", "10X（mpp≈1.00）", 3), ("magnification", "5X", "5X（mpp≈2.00）", 4),
        ("storage_tier", "hot", "热层（NVMe SSD）", 1), ("storage_tier", "warm", "温层（NAS RAID6）", 2),
        ("storage_tier", "cold", "冷层（对象存储归档）", 3),
        ("decision", "positive", "阳性", 1), ("decision", "negative", "阴性", 2),
        ("decision", "rejected", "拒识（转人工）", 3),
        ("confidence", "high", "高置信", 1), ("confidence", "medium", "中置信", 2),
        ("confidence", "low", "低置信", 3),
        ("probe_decision", "triage_out", "分诊排除", 1), ("probe_decision", "escalate", "升级探查", 2),
        ("probe_decision", "confirm", "确认目标区", 3), ("probe_decision", "skip", "跳过", 4),
    ]
    for dict_type, key, label, order in dictionaries:
        db.add(Dictionary(dict_type=dict_type, dict_key=key, dict_label=label, sort_order=order))
    db.flush()


def seed_encoders(db: Session) -> None:
    """把内置编码器声明写进数据库注册表。

    这里显式校验「声明的字段」都必须是 ORM 真实存在的列。
    为什么值得多写这几行：不做校验时，往 EncoderSpec 加一个字段就会让
    `EncoderRegistry(**payload)` 抛 SQLAlchemy 的 TypeError：
    "xxx is an invalid keyword argument" —— 报错信息看不出"你该加一列 + 补一条迁移"，
    而且**只在全新库首次装载时炸**（老库因为记录已存在、走的是 update 分支），
    本地开发几乎不可能碰到，一上 CI 用干净库就全员卡住。
    """
    valid_columns = {c.name for c in EncoderRegistry.__table__.columns}
    for spec in BUILTIN_ENCODERS:
        payload = spec.to_row_dict()
        unknown = sorted(set(payload) - valid_columns)
        if unknown:
            raise RuntimeError(
                f"编码器 {spec.code} 的声明含库中不存在的字段：{unknown}。\n"
                f"  处理方式（两步都要做）：\n"
                f"    1) 在 app/models/modeling.py 的 EncoderRegistry 中补这些列；\n"
                f"    2) 在 app/core/migrations.py 的 MIGRATIONS 末尾追加一条迁移（版本号 +1），\n"
                f"       否则已有环境不会自动加列。\n"
                f"  若该字段是派生值（由其它字段算出），请加入 EncoderSpec.DERIVED_FIELDS。"
            )
        row = db.query(EncoderRegistry).filter_by(code=spec.code).one_or_none()
        if row is None:
            db.add(EncoderRegistry(**payload))
        else:
            row.update_from(payload)
    db.flush()


def seed_compute(db: Session) -> None:
    resources = [
        ("GPU-RENT-A", "训练算力（租用）", "rented", "A100 80G", 8, 80, 128, 1024, 40.0,
         "公有云算力平台", "同城可用区", 28.0, 0.72, False),
        ("GPU-RENT-B", "推理算力（租用）", "rented", "L40S 48G", 4, 48, 64, 512, 20.0,
         "公有云算力平台", "同城可用区", 12.0, 0.55, False),
        ("GPU-GW-01", "国产化算力（信创验证）", "rented", "国产加速卡", 4, 64, 96, 768, 30.0,
         "国产算力服务商", "本地机房", 18.0, 0.31, True),
        ("CPU-EDGE-A", "边缘推理节点（PC 端）", "edge", "CPU only", 0, 0, 32, 128, 8.0,
         "自建", "院内病理科", 0.0, 0.66, False),
    ]
    for (code, name, rtype, gpu, gcount, gmem, cores, mem, storage, vendor, location,
         cost, util, gateway) in resources:
        db.add(ComputeResource(
            code=code, name=name, resource_type=rtype, gpu_model=gpu, gpu_count=gcount,
            gpu_memory_gb=gmem, cpu_cores=cores, memory_gb=mem, storage_tb=storage,
            vendor=vendor, location=location, hourly_cost=cost, utilization=util,
            is_gateway=gateway, status="available",
        ))
    db.flush()


# =============================================================== 数据资产
def seed_assets(db: Session, quick: bool) -> list[Slide]:
    assets = [
        dict(code="DA-INHOUSE", name="院内自有病理切片库（主数据集）",
             source_type="in_hospital", source_org="院内病理科", ethics_no="EC-2023-047",
             organ_system="淋巴造血 / 消化", cancer_type="淋巴结转移 / 消化道早癌",
             year_from=2019, year_to=2025, owner_department="病理科", owner_name="林主任",
             p0_action=True, status="ready",
             notes="多年积累、已由医生完成标注的存量切片，是方案中「比切片数量更稀缺」的核心资产。"),
        dict(code="DA-PARTNER", name="协作医院切片（外部合作）",
             source_type="partner", source_org="协作医院 B", ethics_no="ECB-2024-112",
             organ_system="淋巴造血", cancer_type="淋巴结转移",
             year_from=2021, year_to=2025, owner_department="病理科", owner_name="陈医师",
             p0_action=True, status="ready",
             notes="用于跨中心泛化评估与联邦式增量微调（R3 应对措施）。"),
        dict(code="DA-PUBLIC", name="公开数据集补充",
             source_type="public", source_org="公开病理数据集", ethics_no="公开授权",
             organ_system="泛癌种", cancer_type="泛癌种",
             year_from=2018, year_to=2023, owner_department="算法部", owner_name="赵工",
             p0_action=False, status="profiling",
             notes="三条数据扩展路径之一，用于补充病种覆盖与预训练规模，不进入注册申报数据集。"),
    ]
    for item in assets:
        db.add(DataAsset(
            **item, ethics_approved=True, consent_covered=True, deidentified=True,
            data_boundary="local", staining_types="H&E", slide_count=0, annotated_slide_count=0,
            patient_count=0, total_bytes=0, quality_score=0.0, label_coverage=0.0,
            org_code="ORG-SH-01", site_codes="SITE-A,SITE-B,SITE-C",
        ))
    db.flush()
    asset_map = {a.code: a for a in db.query(DataAsset).all()}

    plan = [
        ("DA-INHOUSE", "SITE-A", 24 if not quick else 10),
        ("DA-PARTNER", "SITE-B", 16 if not quick else 8),
        ("DA-INHOUSE", "SITE-C", 16 if not quick else 8),
    ]
    slides: list[Slide] = []
    index = 0
    for asset_code, site, count in plan:
        for i in range(count):
            is_positive = (i % 2 == 0)
            split = "external" if site == EXTERNAL_SITE else ("val" if i >= count - 4 else "train")
            index += 1
            code = f"{site}-{index:04d}"
            slide = Slide(
                code=code, asset_id=asset_map[asset_code].id, case_no=f"{site}C{index:04d}",
                patient_pseudo_id=f"P{site}{index:04d}", organ="淋巴结",
                cancer_type="淋巴结转移" if is_positive else "淋巴结反应性增生",
                staining="H&E",
                diagnosis_text="转移性腺癌（淋巴结）" if is_positive else "淋巴结反应性增生，未见转移",
                icd_o_3="C77.9" if is_positive else "R59.9",
                magnification="20X", mpp=0.5,
                scanner="Scanner-A1" if site == "SITE-A" else f"Scanner-{site[-1]}",
                split=split, site_code=site, has_lesion=is_positive, org_code="ORG-SH-01",
                status="registered", storage_tier="hot" if i % 3 else "warm",
            )
            db.add(slide)
            slides.append(slide)
    db.flush()

    special = Slide(
        code="SITE-A-SPECIAL", asset_id=asset_map["DA-INHOUSE"].id,
        case_no="SITE-ASPECIAL", patient_pseudo_id="PSPECIAL",
        organ="宫颈", cancer_type="宫颈细胞学", staining="特殊染色（巴氏）",
        diagnosis_text="宫颈细胞学标本（超出本模型能力声明范围）",
        magnification="40X", mpp=0.25, split="test", site_code="SITE-A", org_code="ORG-SH-01",
        has_lesion=False, status="registered", storage_tier="hot",
    )
    db.add(special)
    slides.append(special)
    db.flush()

    thumbs_dir = Path(settings.wsi_dir) / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for slide in slides:
        try:
            reader = open_slide(slide)
            reader.render_thumbnail(320).save(thumbs_dir / f"{slide.code}.png")
            slide.thumbnail_path = str(thumbs_dir / f"{slide.code}.png")
            width, height = reader.dimensions(0)
            slide.width, slide.height = width, height
            slide.level_count = reader.level_count
            slide.lesion_bbox_json = json.dumps(reader.lesion_bbox_at_level0())
            bbox = json.loads(slide.lesion_bbox_json or "[]")
            if bbox:
                x0, y0, x1, y1 = bbox[0], bbox[1], bbox[4], bbox[5]
                slide.lesion_ratio = round(
                    max(0, x1 - x0) * max(0, y1 - y0) / max(width * height, 1), 6
                )
            approx = int(width * height * 3 / 12)  # 按 JPEG 金字塔约 1/12 估算
            slide.file_bytes = approx
            total_bytes += approx
        except Exception as exc:  # pragma: no cover
            _log("切片 %s 缩略图生成失败：%s", slide.code, exc)

    for code, asset in asset_map.items():
        asset_slides = [s for s in slides if s.asset_id == asset.id]
        asset.slide_count = len(asset_slides)
        asset.patient_count = len({s.patient_pseudo_id for s in asset_slides})
        asset.total_bytes = sum(s.file_bytes for s in asset_slides)
    db.flush()

    today = date.today()
    for offset in range(5, -1, -1):
        stat_date = (today - timedelta(days=offset * 7)).isoformat()
        for tier, ratio, media, capacity in (
            ("hot", 0.28, "NVMe SSD 8 TB", int(8 * 1024 ** 4)),
            ("warm", 0.52, "NAS RAID6 48 TB", int(48 * 1024 ** 4)),
            ("cold", 0.20, "对象存储归档", int(200 * 1024 ** 4)),
        ):
            db.add(StorageStat(
                stat_date=stat_date, tier=tier, slide_count=int(len(slides) * ratio),
                bytes_used=int(total_bytes * ratio * (1 + 0.04 * (5 - offset))),
                capacity_bytes=capacity, media=media,
            ))

    extensions = [
        ("increment", "院内增量入库（每月新增）", "DA-INHOUSE", 1200, 380, "", True, True,
         "林主任", "每月滚动", "in_progress", "按月份批入库，同步完成脱敏与伦理台账登记"),
        ("partner", "协作医院 B 数据合作", "DA-PARTNER", 800, 640, "协作医院 B", True, True,
         "陈医师", "第 12 月", "in_progress", "已签数据合作框架协议，按季度交付批次"),
        ("public", "公开数据集补充（泛癌种）", "DA-PUBLIC", 2000, 900, "公开数据平台", False, False,
         "赵工", "持续", "in_progress", "用于扩大预训练覆盖，不进入注册申报数据集"),
    ]
    for (path_type, note, asset_code, target, current, partner, signed, ethics,
         owner, deadline, status, desc) in extensions:
        db.add(AssetExtension(
            asset_id=asset_map[asset_code].id, path_type=path_type,
            target_slide_count=target, current_slide_count=current, partner_name=partner,
            agreement_signed=signed, ethics_required=ethics, owner_name=owner,
            deadline=deadline, status=status, note=f"{note}。{desc}",
        ))
    db.flush()
    _log("  切片 %d 张（含 1 张特殊染色用于演示能力越界拒识）", len(slides))
    return slides


# =============================================================== 标签体系
def seed_labels(db: Session, slides: list[Slide]) -> None:
    schemas = [
        ("LS-CASE-DX", "最终诊断结论", "case", "categorical", ["转移阳性", "转移阴性", "待定"],
         "", "C77.9", True, True, "病例级金标准结论，注册必备"),
        ("LS-CASE-AGE", "患者年龄分层", "case", "categorical", ["<40", "40-60", ">60"],
         "", "", False, False, "用于亚组分析"),
        ("LS-CASE-TREAT", "新辅助治疗史", "case", "boolean", [], "", "", False, False,
         "可能影响形态学判读的临床信息"),
        ("LS-SLIDE-ORGAN", "标本部位", "slide", "categorical",
         ["淋巴结", "胃", "食管", "结直肠", "宫颈"], "", "", True, True, "注册必备"),
        ("LS-SLIDE-STAIN", "染色类型", "slide", "categorical",
         ["H&E", "IHC", "特殊染色（巴氏）"], "", "", True, True, "注册必备；能力声明范围判定的输入"),
        ("LS-SLIDE-QUALITY", "制片质量评估", "slide", "categorical",
         ["优", "良", "可判读", "不可判读"], "", "", True, False, "决定该切片是否进入训练与评测集"),
        ("LS-SLIDE-TUMOR", "肿瘤占比（切片级）", "slide", "numeric", [], "%", "", False, True,
         "注册必备；影响判读可靠性"),
        ("LS-SLIDE-SUBTYPE", "组织学亚型", "slide", "categorical",
         ["腺癌", "鳞癌", "小细胞癌", "未见肿瘤"], "", "", False, False, "细化亚型分类任务"),
        ("LS-REGION-LESION", "病灶区域框", "region", "bbox", [], "", "", True, True,
         "区域级标注，是图块级模型监督信号的核心来源"),
        ("LS-REGION-MARGIN", "切缘状态", "region", "categorical",
         ["切缘阴性", "切缘阳性", "无法评估"], "", "", False, False, "与手术决策直接相关"),
        ("LS-REGION-VASCULAR", "脉管侵犯", "region", "boolean", [], "", "", False, False, ""),
        ("LS-REGION-NECROSIS", "坏死区域", "region", "bbox", [], "", "", False, False, ""),
        ("LS-CELL-NUCLEUS", "细胞核坐标点", "cell", "bbox", [], "", "", False, False,
         "细胞级标注，支撑细胞学任务与核形态学量化"),
        ("LS-CELL-MITOSIS", "核分裂计数", "cell", "numeric", [], "个/10HPF", "", False, False, "分级关键指标"),
        ("LS-CELL-PLEOMORPHISM", "核多形性", "cell", "categorical",
         ["轻度", "中度", "重度"], "", "", False, False, ""),
        ("LS-QC-AGREE", "标注一致性判定", "qc", "categorical",
         ["一致", "部分一致", "不一致"], "", "", False, False, "质控层：驱动仲裁流程"),
        ("LS-QC-IMAGE", "图像质量缺陷", "qc", "categorical",
         ["无缺陷", "染色偏浅", "刀痕", "气泡", "折叠"], "", "", False, False, "多选"),
        ("LS-QC-ARBITRATION", "仲裁结论", "qc", "categorical",
         ["采纳原标注", "修正标注", "上报上级医师"], "", "", False, False, ""),
    ]
    numeric_range = {"LS-SLIDE-TUMOR": (0, 100), "LS-CELL-MITOSIS": (0, 200)}
    for order, (code, name, layer, vtype, values, unit, icd, req_train, req_reg, desc) in enumerate(schemas):
        low, high = numeric_range.get(code, (0.0, 1.0))
        db.add(LabelSchema(
            code=code, name=name, layer=layer, value_type=vtype,
            allowed_values_json=json.dumps(values, ensure_ascii=False), unit=unit,
            min_value=low if vtype == "numeric" else None,
            max_value=high if vtype == "numeric" else None,
            icd_o_3_code=icd, term_source="本院病理术语表 + ICD-O-3" if icd else "本院病理术语表",
            required_for_training=req_train, required_for_registration=req_reg,
            description=desc, sort_order=order, multi_select=(code == "LS-QC-IMAGE"),
            applicable_stainings="H&E/特殊染色（巴氏）" if layer == "cell" else "H&E",
        ))
    db.flush()

    sops = [
        ("SOP-LABEL-001", "数字病理切片四层标签标注标准作业程序", "v2.1",
         "覆盖病例级/切片级/区域级/细胞级四层标签的定义、边界与典型图示",
         "林主任", "approved", "林主任",
         "同一标签出现两名标注者不一致时：① 双方各自书面陈述依据；② 由亚专科副主任医师仲裁；"
         "③ 仍不一致则上报首席医学官终裁，全过程留痕。"),
        ("SOP-LABEL-002", "标注人员资质与培训管理办法", "v1.3",
         "规定标注人员准入、培训学时、资格核验与定期复训要求", "林主任", "approved", "林主任",
         "同一标注者对同一例的重复标注不一致时，取最近一次并经质控复核。"),
        ("SOP-LABEL-003", "标注质控与抽检规程", "v1.0",
         "规定抽检比例（不低于 15%）、缺陷类型定义与返工流程", "陈医师", "approved", "林主任",
         "质控发现系统性偏差时，暂停该标注者任务并重新培训。"),
        ("SOP-LABEL-004", "区域级与细胞级标注操作细则", "v0.9",
         "区域框与细胞坐标点的绘制规范、最小面积与最小数量要求", "吴医师", "pending", "",
         "待医学审核通过后生效。"),
    ]
    for (code, name, version, scope, owner, status, reviewer, rule) in sops:
        db.add(LabelSop(
            code=code, name=name, version=version, scope=scope, owner_name=owner,
            medical_review_status=status, medical_reviewer=reviewer,
            medical_reviewed_at="2026-09-18" if status == "approved" else "",
            arbitration_rule=rule, content=f"（SOP 正文略）本文件规定{scope}。版本 {version}。",
            effective_date="2026-10-01" if status == "approved" else "",
            status="effective" if status == "approved" else "draft",
        ))
    db.flush()

    annotators = [
        ("林主任", "cmo", "主任医师", "消化系统病理", "本院", 22, 4200, "ZG-2019-0088", 96.0, True, "林主任"),
        ("陈医师", "doctor01", "副主任医师", "淋巴造血系统病理", "本院", 14, 3600, "ZG-2021-0451", 72.0, True, "林主任"),
        ("吴医师", "doctor02", "主治医师", "消化系统病理", "本院", 8, 2800, "ZG-2023-1102", 64.0, True, "林主任"),
        ("何医师", "doctor01", "主治医师", "妇科病理", "协作医院 B", 7, 2400, "ZG-2023-1188", 48.0, True, "林主任"),
        ("徐技师", "doctor02", "技师", "数字病理扫描与质控", "本院", 5, 5200, "ZG-2024-0231", 40.0, True, "陈医师"),
        ("马医师", "doctor02", "住院医师", "病理科住院医师规培", "本院", 3, 1800, "", 24.0, False, ""),
    ]
    user_map = {u.username: u for u in db.query(User).all()}
    profiles: list[AnnotatorProfile] = []
    for (name, username, title, subspecialty, hospital, years, volume, cert, hours,
         verified, verifier) in annotators:
        profile = AnnotatorProfile(
            user_id=user_map[username].id, name=name, title=title, subspecialty=subspecialty,
            hospital=hospital, years_experience=years, annual_slide_volume=volume,
            certificate_no=cert,
            training_records_json=json.dumps([
                {"date": "2026-03-12", "course": "四层标签体系标注规范", "hours": 8},
                {"date": "2026-06-05", "course": "区域框与细胞点标注工具实操", "hours": 6},
            ], ensure_ascii=False),
            training_hours=hours, qualification_verified=verified, verified_by=verifier,
            verified_at="2026-09-20" if verified else "",
            employee_no=user_map[username].employee_no,
        )
        db.add(profile)
        profiles.append(profile)
    db.flush()

    schemas_by_code = {s.code: s for s in db.query(LabelSchema).all()}
    rng = random.Random(20260129)
    he_slides = [s for s in slides if s.staining == "H&E"]
    annotation_count = 0

    for slide in he_slides:
        annotator = rng.choice(profiles[:4])
        for schema_code, value_text, elapsed, status in (
            ("LS-SLIDE-STAIN", "H&E", rng.randint(4, 12), "qc_passed"),
            ("LS-SLIDE-ORGAN", "淋巴结", rng.randint(3, 8), "qc_passed"),
            ("LS-SLIDE-QUALITY", "优" if rng.random() < 0.55 else ("良" if rng.random() < 0.85 else "可判读"),
             rng.randint(5, 15), "qc_passed"),
        ):
            db.add(Annotation(
                slide_id=slide.id, slide_code=slide.code, schema_id=schemas_by_code[schema_code].id,
                schema_code=schema_code, layer="slide", annotator_id=annotator.id,
                annotator_name=annotator.name, value_text=value_text, confidence=1.0,
                elapsed_sec=elapsed, tool="web", status=status,
            ))
            annotation_count += 1
        db.add(Annotation(
            slide_id=slide.id, slide_code=slide.code, schema_id=schemas_by_code["LS-SLIDE-TUMOR"].id,
            schema_code="LS-SLIDE-TUMOR", layer="slide", annotator_id=annotator.id,
            annotator_name=annotator.name,
            value_num=round(rng.uniform(35, 88) if slide.has_lesion else rng.uniform(2, 25), 1),
            confidence=0.9, elapsed_sec=rng.randint(20, 60), tool="web", status="qc_passed",
        ))
        annotation_count += 1

        dx_value = "转移阳性" if slide.has_lesion else "转移阴性"
        db.add(Annotation(
            slide_id=slide.id, slide_code=slide.code, schema_id=schemas_by_code["LS-CASE-DX"].id,
            schema_code="LS-CASE-DX", layer="case", annotator_id=profiles[0].id,
            annotator_name=profiles[0].name, value_text=dx_value, confidence=1.0,
            elapsed_sec=rng.randint(15, 40), tool="web", status="final",
        ))
        annotation_count += 1
        if rng.random() < 0.42:
            second = rng.choice(profiles[1:4])
            second_value = dx_value
            if rng.random() < 0.20:
                second_value = "待定" if slide.has_lesion else "转移阳性"
            db.add(Annotation(
                slide_id=slide.id, slide_code=slide.code, schema_id=schemas_by_code["LS-CASE-DX"].id,
                schema_code="LS-CASE-DX", layer="case", annotator_id=second.id,
                annotator_name=second.name, value_text=second_value, confidence=0.85,
                elapsed_sec=rng.randint(15, 45), tool="web", status="submitted",
            ))
            annotation_count += 1

        if slide.has_lesion:
            reader = open_slide(slide)
            mask = reader.lesion_mask_at(1)
            if mask is not None and mask.any():
                ys, xs = np.where(mask)
                boxes = []
                for chunk in np.array_split(np.arange(xs.size), 3):
                    if chunk.size == 0:
                        continue
                    cx, cy = xs[chunk], ys[chunk]
                    boxes.append({"level": 1, "x": int(cx.min()), "y": int(cy.min()),
                                  "w": int(cx.max() - cx.min()), "h": int(cy.max() - cy.min())})
                db.add(Annotation(
                    slide_id=slide.id, slide_code=slide.code,
                    schema_id=schemas_by_code["LS-REGION-LESION"].id, schema_code="LS-REGION-LESION",
                    layer="region", annotator_id=annotator.id, annotator_name=annotator.name,
                    value_text="转移灶", region_json=json.dumps(boxes, ensure_ascii=False),
                    confidence=0.92, elapsed_sec=rng.randint(60, 180), tool="web", status="qc_passed",
                ))
                annotation_count += 1

    qc_count = 0
    for slide in he_slides[: max(6, len(he_slides) // 3)]:
        reviewer = rng.choice(profiles[:4])
        passed = rng.random() < 0.82
        db.add(QcRecord(
            slide_id=slide.id, slide_code=slide.code, qc_type="sampling",
            reviewer_name=reviewer.name, result="pass" if passed else "rework",
            score=round(rng.uniform(0.85, 1.0) if passed else rng.uniform(0.5, 0.75), 4),
            defect_types_json=json.dumps([] if passed else ["区域框边界不精确"], ensure_ascii=False),
            rework_required=not passed,
            reviewed_at=(datetime.now() - timedelta(days=rng.randint(1, 40))).isoformat(timespec="seconds"),
            note="抽检合格" if passed else "区域框边界需返工，已通知原标注者",
        ))
        qc_count += 1

    db.add(Arbitration(
        slide_id=he_slides[0].id, slide_code=he_slides[0].code,
        schema_id=schemas_by_code["LS-CASE-DX"].id, schema_code="LS-CASE-DX",
        conflict_summary="两名医师对微小转移灶的判读存在分歧：一方判为转移阳性，一方判为待定",
        opinions_json=json.dumps([
            {"annotator": profiles[0].name, "value": "转移阳性", "confidence": 0.95,
             "reason": "可见成簇异型上皮细胞，核浆比增高，符合转移灶表现"},
            {"annotator": profiles[2].name, "value": "待定", "confidence": 0.70,
             "reason": "病灶体积较小，需免疫组化辅助确认"},
        ], ensure_ascii=False),
        rule_applied="SOP-LABEL-001 第 4.3 条：双方书面陈述依据后由亚专科副主任医师仲裁",
        final_value="转移阳性", arbitrator_name=profiles[1].name, arbitrator_title="副主任医师",
        status="resolved",
        decided_at=(datetime.now() - timedelta(days=12)).isoformat(timespec="seconds"),
    ))
    db.add(Arbitration(
        slide_id=he_slides[3].id, slide_code=he_slides[3].code,
        schema_id=schemas_by_code["LS-SLIDE-TUMOR"].id, schema_code="LS-SLIDE-TUMOR",
        conflict_summary="肿瘤占比量化差异超过 15 个百分点（32% vs 48%）",
        opinions_json=json.dumps([
            {"annotator": profiles[1].name, "value": "32", "confidence": 0.80, "reason": "以典型肿瘤区域估算"},
            {"annotator": profiles[2].name, "value": "48", "confidence": 0.75, "reason": "纳入可疑浸润区域"},
        ], ensure_ascii=False),
        rule_applied="SOP-LABEL-001 第 4.5 条：量化标签差异超过预设阈值时由上级医师终裁",
        final_value="40", arbitrator_name=profiles[0].name, arbitrator_title="主任医师",
        status="resolved",
        decided_at=(datetime.now() - timedelta(days=6)).isoformat(timespec="seconds"),
    ))
    db.flush()

    annotated_codes = {a.slide_code for a in db.query(Annotation).all()}
    for asset in db.query(DataAsset).all():
        asset_slides = [s for s in slides if s.asset_id == asset.id]
        asset.annotated_slide_count = sum(1 for s in asset_slides if s.code in annotated_codes)
        asset.label_coverage = round(asset.annotated_slide_count / max(len(asset_slides), 1), 6)
        asset.quality_score = round(0.72 + 0.25 * asset.label_coverage, 4)
    db.flush()
    _log("  标签定义 %d 项（四层 + 质控层），标注记录 %d 条，质控 %d 条，仲裁 2 条",
                len(schemas), annotation_count, qc_count)


# =============================================================== 模型基座
def seed_model(db: Session) -> ModelBase:
    base = ModelBase(
        code="SH-PATH-V1", name="蓝天健康病理垂类模型",
        organ_scope="淋巴造血系统 / 消化系统",
        cancer_types_json=json.dumps(["淋巴结转移", "消化道早癌"], ensure_ascii=False),
        task_scope_json=json.dumps(["lymph_node_metastasis", "gi_early_cancer"], ensure_ascii=False),
        default_encoder_code="hibou-b-synth", fallback_encoder_code="sh-encoder-b0",
        mil_arch="ABMIL-Gated", track="commercial", current_stage="Stage C",
        description=(
            "商用主线基座：图块级特征模型 + 切片级注意力聚合。默认编码器为可商用许可路线"
            "（Hibou，Apache-2.0），并行孵化自研编码器（sh-encoder-b0），"
            "以在第 16 个月完成替换、彻底消除许可风险（M4 里程碑）。"
        ),
        owner_name="赵工",
    )
    db.add(base)
    db.add(ModelBase(
        code="SH-PATH-AGENT-V1", name="智慧医疗 Agent（探索线）",
        organ_scope="淋巴造血系统",
        cancer_types_json=json.dumps(["淋巴结转移"], ensure_ascii=False),
        task_scope_json=json.dumps(["multimodal_report", "differential_diagnosis"], ensure_ascii=False),
        default_encoder_code="uni2-h", fallback_encoder_code="sh-encoder-l1",
        mil_arch="ABMIL-Gated + Multi-Agent", track="exploration", current_stage="Stage D",
        description=(
            "探索线：全切片多模态推理与五智能体协同，承载于科研与增益侧，"
            "不进入商用主线的注册申报范围。使用非商用权重（UNI2-h）并在 research 环境验证。"
        ),
        owner_name="孙工",
    ))
    db.flush()

    db.add(AgentCapability(
        code="AC-SH-01", model_base_id=base.id, supported_stainings="H&E",
        supported_organs_json=json.dumps(["淋巴结", "胃", "食管", "结直肠"], ensure_ascii=False),
        supported_tasks_json=json.dumps(["lymph_node_metastasis", "gi_early_cancer"], ensure_ascii=False),
        unsupported_json=json.dumps([
            "冰冻切片（术中快速病理）", "细胞学涂片（如宫颈巴氏涂片）",
            "特殊染色与免疫组化（IHC）定量", "非 H&E 染色的数字化切片",
        ], ensure_ascii=False),
        min_tissue_ratio=0.10, max_mpp=1.0,
        declaration_text=(
            "本模型适用于 H&E 染色的组织学全切片图像（mpp ≤ 1.0，即 10X 及以上扫描分辨率），"
            "在已声明的病种范围内输出辅助提示与可追溯的判断依据。"
            "不适用于冰冻切片、细胞学涂片、特殊染色与免疫组化切片；"
            "本模型不提供最终诊断，最终诊断由病理医师作出。"
        ),
        status="active",
    ))
    db.flush()
    return base


# =============================================================== 云边协同
def seed_edge(db: Session) -> None:
    nodes = [
        dict(code="EDGE-A-01", name="院内主中心边缘节点", hospital="院内主中心", site_code="SITE-A",
             node_type="edge_server", region="本院机房", cpu_cores=64, memory_gb=256,
             gpu_model="L40S", gpu_count=2, storage_tb=40.0, deployment_mode="local",
             edge_runtime="院内推理服务（GPU）", realtime_inference=True,
             local_slide_count=24, daily_case_capacity=320, latency_ms=180, uptime_rate=0.998,
             status="online"),
        dict(code="EDGE-B-01", name="协作医院 B 边缘节点", hospital="协作医院 B", site_code="SITE-B",
             node_type="edge_server", region="同城机房", cpu_cores=32, memory_gb=128,
             gpu_model="L40S", gpu_count=1, storage_tb=20.0, deployment_mode="edge_cloud",
             edge_runtime="院内推理服务（GPU）", realtime_inference=True,
             local_slide_count=16, daily_case_capacity=160, latency_ms=260, uptime_rate=0.991,
             status="online"),
        dict(code="EDGE-C-01", name="外部验证中心 C 边缘节点", hospital="外部验证中心 C",
             site_code="SITE-C", node_type="edge_server", region="异地机房",
             cpu_cores=32, memory_gb=128, gpu_model="L40S", gpu_count=1, storage_tb=20.0,
             deployment_mode="edge_cloud", edge_runtime="院内推理服务（GPU）",
             realtime_inference=True, local_slide_count=16, daily_case_capacity=140,
             latency_ms=310, uptime_rate=0.986, status="online"),
        dict(code="EDGE-GW-01", name="县域医联体一体机（基层）", hospital="县域人民医院",
             site_code="SITE-GW", node_type="gateway", region="县域",
             cpu_cores=16, memory_gb=64, gpu_model="", gpu_count=0, storage_tb=8.0,
             deployment_mode="edge_cloud", edge_runtime="ONNX Runtime（CPU）",
             realtime_inference=True, local_slide_count=4, daily_case_capacity=60,
             latency_ms=620, uptime_rate=0.972, status="online"),
        dict(code="EDGE-PC-01", name="病理科 PC 端推理节点", hospital="院内主中心",
             site_code="SITE-A", node_type="pc", region="病理科阅片室",
             cpu_cores=16, memory_gb=32, gpu_model="", gpu_count=0, storage_tb=2.0,
             deployment_mode="local", edge_runtime="ONNX Runtime（CPU）",
             realtime_inference=True, local_slide_count=2, daily_case_capacity=40,
             latency_ms=850, uptime_rate=0.995, status="online"),
        dict(code="EDGE-D-01", name="待接入备用节点", hospital="协作医院 D", site_code="SITE-D",
             node_type="edge_server", region="同城机房", cpu_cores=32, memory_gb=128,
             gpu_model="L40S", gpu_count=1, storage_tb=20.0, deployment_mode="edge_cloud",
             edge_runtime="", realtime_inference=False, local_slide_count=0,
             daily_case_capacity=0, latency_ms=0, uptime_rate=0.0, status="offline"),
    ]
    for item in nodes:
        db.add(EdgeNode(**item, last_heartbeat=datetime.now().isoformat(timespec="seconds")
                        if item["status"] == "online" else "",
                        deploy_minutes=1 if item["node_type"] in ("pc", "gateway") else 3))
    db.flush()


# =============================================================== 注册与风险
def seed_registration(db: Session) -> None:
    registry_service.ensure_registration_plan(db)
    plan_targets = {
        "M1": (8, "done", 1.0), "M2": (12, "done", 1.0),
        "M3": (18, "in_progress", 0.62), "M4": (26, "in_progress", 0.35),
        "M5": (12, "pending", 0.0), "M6": (6, "pending", 0.0),
        "M7": (0, "pending", 0.0), "M8": (0, "pending", 0.0),
    }
    done_days, status_map = {}, {}
    for milestone in db.query(registry_service.RegistrationMilestone).all():
        days, status, progress = plan_targets.get(milestone.code, (0, "pending", 0.0))
        done_days[milestone.id] = days
        status_map[milestone.id] = status
        milestone.status = status
        milestone.progress = progress
        if days:
            milestone.actual_date = (date.today() - timedelta(days=days)).isoformat()
        milestone.evidence_refs_json = json.dumps(_milestone_evidence(milestone.code), ensure_ascii=False)
    db.flush()

    sites = [
        ("CT-01", "院内主中心", "本院", "lead", "approved", "signed", "林主任", "主任医师",
         120, 46, 0.52, "2026-10-15", "enrolling"),
        ("CT-02", "协作医院 B", "同城", "participating", "approved", "signed", "何医师", "副主任医师",
         80, 28, 0.50, "2026-10-20", "enrolling"),
        ("CT-03", "外部验证中心 C", "异地", "participating", "submitted", "negotiating", "待定",
         "主任医师", 70, 0, 0.55, "", "preparing"),
        ("CT-04", "省级肿瘤医院", "异地", "participating", "pending", "pending", "待定",
         "主任医师", 60, 0, 0.48, "", "preparing"),
    ]
    for (code, hospital, city, site_type, ethics, contract, pi, title, target, enrolled,
         pos_rate, start, status) in sites:
        db.add(ClinicalTrialSite(
            code=code, hospital=hospital, city=city, site_type=site_type,
            ethics_status=ethics, contract_status=contract, pi_name=pi, pi_title=title,
            target_cases=target, enrolled_cases=enrolled,
            enrollment_rate=round(enrolled / max(target, 1), 6), positive_rate=pos_rate,
            start_date=start, status=status,
            note="参与中心以 MRMC 方式设计对照，AI 与两名阅片者独立判读同一批病例。",
        ))
    db.flush()
    _log("  注册计划已建立：4 个阶段、8 个里程碑、10 项风险、6 份法规依据、4 个临床中心")


def _milestone_evidence(code: str) -> list[dict[str, str]]:
    return {
        "M1": [
            {"type": "report", "label": "《数据资产盘点与标签体系说明书》", "ref": "ASSET-INV-V1"},
            {"type": "sop", "label": "标注 SOP 医学审核记录", "ref": "SOP-LABEL-001"},
            {"type": "api", "label": "标签覆盖率报告接口", "ref": "GET /api/v1/labels/coverage"},
        ],
        "M2": [
            {"type": "api", "label": "评测基座运行记录", "ref": "GET /api/v1/eval/runs"},
            {"type": "model", "label": "基线模型版本与指标留档", "ref": "SH-PATH-V1-v1.0.0"},
        ],
        "M3": [
            {"type": "api", "label": "内部验证集评测结果", "ref": "DS-INT-VAL"},
            {"type": "api", "label": "外部多中心验证结果", "ref": "DS-EXT-C"},
            {"type": "audit", "label": "评测运行审计记录", "ref": "run_eval"},
        ],
        "M4": [
            {"type": "model", "label": "自研编码器对照版本", "ref": "SH-PATH-V1-v0.9.0-selfdev"},
            {"type": "api", "label": "许可风险体检报告", "ref": "GET /api/v1/models/encoders/license-audit"},
        ],
        "M5": [],
        "M6": [
            {"type": "record", "label": "伦理批件与首例入组记录", "ref": "CT-01"},
        ],
        "M7": [],
        "M8": [],
    }.get(code, [])


# =============================================================== 合规台账
def seed_compliance_static(db: Session) -> None:
    db.add(EthicsRecord(
        code="ETH-01", asset_id=1, hospital="院内主中心",
        committee="医院伦理委员会", ethics_no="EC-2023-047",
        approval_date="2023-05-18", valid_until="2028-05-17",
        scope="院内既往病理切片用于人工智能辅助诊断系统研发与注册申报",
        use_purpose="产品开发 + 注册申报", status="approved", owner_name="林主任",
        note="审批范围已覆盖产品开发与注册申报两个用途，无需二次审批。",
    ))
    db.add(EthicsRecord(
        code="ETH-02", asset_id=2, hospital="协作医院 B",
        committee="协作医院伦理委员会", ethics_no="ECB-2024-112",
        approval_date="2024-03-22", valid_until="2029-03-21",
        scope="协作医院病理切片用于多中心验证与联邦式模型增量训练",
        use_purpose="多中心验证 + 联邦训练", status="approved", owner_name="陈医师",
        note="联邦训练场景已明确样本不出域，仅上传模型参数更新。",
    ))
    db.add(EthicsRecord(
        code="ETH-03", asset_id=3, hospital="公开数据集",
        committee="数据提供方授权", ethics_no="PUBLIC-LICENSE",
        approval_date="2025-01-10", valid_until="", scope="公开数据集按其原始许可用于科研预训练",
        use_purpose="科研预训练", status="approved", owner_name="赵工",
        note="不进入注册申报数据集，仅用于扩大预训练覆盖。",
    ))

    db.add(ConsentRecord(
        code="CS-01", asset_id=1, consent_type="broad", case_count=680, covered_count=662,
        coverage_rate=round(662 / 680, 6), waiver_granted=False,
        document_ref="泛知情同意书模板 V3 + 逐例签署台账", status="valid",
        last_audit_at=(datetime.now() - timedelta(days=20)).isoformat(timespec="seconds"),
    ))
    db.add(ConsentRecord(
        code="CS-02", asset_id=2, consent_type="study", case_count=320, covered_count=308,
        coverage_rate=round(308 / 320, 6), waiver_granted=False,
        document_ref="多中心研究知情同意书 + 分中心台账", status="valid",
        last_audit_at=(datetime.now() - timedelta(days=14)).isoformat(timespec="seconds"),
    ))
    db.add(ConsentRecord(
        code="CS-03", asset_id=3, consent_type="waived", case_count=900, covered_count=900,
        coverage_rate=1.0, waiver_granted=True,
        waiver_reason="公开数据集已由数据提供方完成伦理审查与去标识化，按其许可条款使用",
        waiver_approved_by="林主任", document_ref="公开数据集使用许可与伦理声明", status="valid",
    ))

    assessments = [
        ("SEC-01", "软件产品第三方检测（GB/T 25000.51）", "third_party_test",
         "国家医疗器械检测中心", "WT-2026-0417", "passed", "2026-09-12", "2029-09-11",
         "涵盖功能性、性能效率、兼容性、易用性、可靠性、信息安全性与维护性。"),
        ("SEC-02", "网络安全测评", "network_security",
         "省级网络安全测评中心", "NS-2026-1028", "passed", "2026-09-25", "2027-09-24",
         "含漏洞扫描与渗透测试；数据传输与存储加密符合要求。"),
        ("SEC-03", "软件版本定版与配置管理核查", "software_freeze",
         "内部质量部", "QF-2026-0031", "passed", "2026-10-08", "",
         "软件定版记录、版本控制与变更管理流程核查通过。"),
        ("SEC-04", "质量管理体系（QMS）认证", "third_party_test",
         "认证机构", "QMS-2026-0088", "pending", "", "",
         "预计在 P2 阶段完成认证。"),
    ]
    for (code, name, atype, org, report_no, result, at, until, note) in assessments:
        db.add(SecurityAssessment(
            code=code, name=name, assessment_type=atype, organization=org,
            report_no=report_no, result=result, assessed_at=at, valid_until=until,
            owner_name="周经理", note=note,
            issues_json=json.dumps([] if result == "passed" else ["认证审核排期中"], ensure_ascii=False),
        ))

    answers = [
        # 问一：数据可溯源
        ("RQ-1-1", "data_traceability", "每一例数据的来源、伦理审批与知情同意是否可逐例追溯？",
         "可逐例追溯。每张切片在入库时登记资产批次、来源机构、伦理批件号与病例伪匿名编号；"
         "知情同意按案例台账登记覆盖率；所有登记动作写入不可篡改的审计哈希链。",
         ["ETH-01", "ETH-02", "CS-01", "CS-02", "GET /api/v1/compliance/audit-chain/verify"],
         "《人工智能医疗器械注册审查指导原则》数据集构建要求", "周经理", "ready"),
        ("RQ-1-2", "data_traceability", "标注人员的资质与标注过程是否可证明？",
         "可证明。标注人员均建立资质档案（职称、亚专科方向、年阅片量、资格证书、培训学时），"
         "标注 SOP 经医学审核后生效；多名专家意见冲突时按 SOP 规定的仲裁规则处理并全程留痕。",
         ["SOP-LABEL-001", "GET /api/v1/labels/annotators", "GET /api/v1/labels/consistency"],
         "《人工智能医疗器械注册审查指导原则》数据标注要求", "林主任", "ready"),
        ("RQ-1-3", "data_traceability", "训练数据是否与评测数据严格隔离？是否存在数据泄漏？",
         "严格隔离。数据集按 train/val/test/external 划分并记录中心编号；"
         "评测集冻结后禁止增删成员；相似病例检索按病例号排除同病例的其他切片，避免泄漏式「相似」。",
         ["GET /api/v1/eval/datasets", "DS-INT-VAL", "DS-EXT-C"],
         "《人工智能医疗器械注册审查指导原则》数据集划分要求", "赵工", "ready"),
        # 问二：算法可解释
        ("RQ-2-1", "algorithm_explainability", "算法决策的空间依据能否定位到具体区域？",
         "可以。采用图块级特征模型 + 切片级注意力聚合（ABMIL），注意力权重经 softmax 归一化后"
         "直接映射回切片坐标，可给出候选区域的位置、倍率与权重占比，并在前端叠加热力图。",
         ["GET /api/v1/compliance/explainability", "GET /api/v1/agents/sessions/{id}"],
         "《人工智能医疗器械注册审查指导原则》算法可解释性要求", "赵工", "ready"),
        ("RQ-2-2", "algorithm_explainability", "形态学描述是否由算法生成？是否存在「幻觉」风险？",
         "描述由实测图像统计量驱动（颜色去卷积得到的核占比、核聚集倍数、核尺寸代理量、核浆比等），"
         "未达阈值的表述不生成；同时采用证据强制引用、置信度校准、拒识、人在环路四重防控降低幻觉风险。",
         ["GET /api/v1/compliance/explainability", "GET /api/v1/agents/sessions/{id}/evidence"],
         "《人工智能医疗器械注册审查指导原则》算法可解释性与风险控制要求", "赵工", "ready"),
        ("RQ-2-3", "algorithm_explainability", "模型在什么情况下会拒绝给出结论？",
         "五重拒识：能力边界越界、未检出有效组织、组织占比过低、校准后置信度低于阈值、"
         "多轨迹投票一致率低于 2/3。命中任一条件即拒绝给出结论、转人工复核，并落库拒识原因。",
         ["GET /api/v1/agents/metrics", "GET /api/v1/agents/tickets"],
         "《人工智能医疗器械注册审查指导原则》人机交互与安全要求", "林主任", "ready"),
        # 问三：临床可验证
        ("RQ-3-1", "clinical_validity", "临床试验如何设计？是否以 MRMC 方式对照人工判读？",
         "以多阅片者多病例（MRMC）方式设计：同一批病例由 AI 与两名阅片者独立判读，"
         "以配对自举比较 AUC 差异并给出置信区间与 p 值；AI 不替代医生终审，"
         "医生终审判读一致性单独统计。",
         ["GET /api/v1/eval/mrmc", "CT-01", "CT-02"],
         "《人工智能医疗器械注册审查指导原则》临床评价要求", "周经理", "ready"),
        ("RQ-3-2", "clinical_validity", "是否开展外部多中心验证？跨中心性能衰减如何控制？",
         "已开展。方案中期即启动多中心验证，评测基座按中心分组统计指标并计算衰减幅度；"
         "控制措施包括染色归一化、中心不变性训练与联邦式增量微调。",
         ["DS-EXT-C", "GET /api/v1/eval/runs", "GET /api/v1/edge/overview"],
         "《人工智能医疗器械注册审查指导原则》多中心验证要求", "赵工", "ready"),
        ("RQ-3-3", "clinical_validity", "模型迭代是否需要重新注册？",
         "若为核心算法不变的性能优化，可走 2025 年第 63 号公告明确的简化变更注册通道；"
         "涉及核心算法、适应症或预期用途变更时需重新申报。系统对锁定的注册基线版本禁止就地修改。",
         ["GD-02", "GET /api/v1/compliance/change-registrations"],
         "国家药监局 2025 年第 63 号公告", "周经理", "ready"),
    ]
    for order, (code, group, question, answer, refs, regulation, owner, status) in enumerate(answers):
        db.add(ReviewQuestionAnswer(
            code=code, group_key=group, question=question, answer=answer,
            evidence_refs_json=json.dumps(refs, ensure_ascii=False),
            regulation_ref=regulation, owner_name=owner, status=status, sort_order=order,
        ))

    db.add(ChangeRegistration(
        code="CR-01", title="评测基座精度优化（核心算法不变）",
        change_type="performance_optimization",
        from_version="SH-PATH-V1-v1.0.0", to_version="SH-PATH-V1-v1.1.0",
        algorithm_unchanged=True,
        impact_analysis=(
            "仅优化特征预计算的数值稳定性与注意力聚合的权重初始化，模型结构与核心算法未变；"
            "已验证内部与外部验证集指标不劣于原版本。"
        ),
        verification_ref="回归评测集 DS-REGRESSION",
        status="draft", owner_name="周经理",
        note="依据 2025 年第 63 号公告的「核心算法不变而性能优化」简化通道申报。",
    ))
    db.flush()
    _log("  合规台账：伦理 3 份、知情同意 3 份、检测测评 4 项、审评应答 9 条、变更注册 1 条")


# =============================================================== 运营
def seed_ops(db: Session) -> None:
    ops_service.ensure_ops_plan(db)
    from app.models.ops import TeamRole

    roles = db.query(TeamRole).all()
    suggestion = sum(r.headcount_suggested for r in roles)
    _log("  运营计划：团队编制 %d 人（区间 %d—%d）、成本结构 %d 项、收益路径 %d 条",
                suggestion, sum(r.headcount_min for r in roles),
                sum(r.headcount_max for r in roles),
                6, 5)


def seed_all_static(db: Session, quick: bool = False) -> dict:
    """灌入全部静态数据，返回运行期所需的上下文。"""
    started = time.time()
    _log("[1/9] 系统与权限…")
    seed_system(db)
    seed_encoders(db)
    seed_compute(db)

    _log("[2/9] 数据资产与切片（确定性合成 WSI + 缩略图）…")
    slides = seed_assets(db, quick)

    _log("[3/9] 四层标签体系、标注与质控…")
    seed_labels(db, slides)

    _log("[4/9] 模型基座与能力声明…")
    base = seed_model(db)

    _log("[5/9] 云边协同节点…")
    seed_edge(db)

    _log("[6/9] 注册路径、里程碑与风险台账…")
    seed_registration(db)

    _log("[7/9] 合规台账（伦理 / 知情同意 / 检测 / 审评应答）…")
    seed_compliance_static(db)

    _log("[8/9] 运营编制与投入结构…")
    seed_ops(db)

    db.commit()
    _log("[9/9] 静态数据完成（%.1fs）", time.time() - started)
    return {"slides": slides, "base": base}

