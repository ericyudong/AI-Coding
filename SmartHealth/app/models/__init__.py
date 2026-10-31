"""全部 ORM 实体注册入口。

导入本包即完成所有实体向 Base.metadata 的注册（init_db 依赖该副作用）。
"""

from app.models.agent import (
    AGENT_ROLE_LABELS,
    AGENT_ROLES,
    MAGNIFICATION_LADDER,
    AgentCapability,
    AgentDiagnosis,
    AgentEvidence,
    AgentProbe,
    AgentSession,
    AgentStep,
    AgentVote,
    ReviewTicket,
)
from app.models.asset import AssetExtension, DataAsset, Slide, SlideFeature, StorageStat
from app.models.base import BaseModel, CodeNameMixin, TimestampMixin, utcnow
from app.models.compliance import (
    REVIEW_GROUP_LABELS,
    REVIEW_GROUPS,
    AuditChainRecord,
    ChangeRegistration,
    ConsentRecord,
    DataBoundaryCheck,
    EthicsRecord,
    ExplainabilityPackage,
    ReviewQuestionAnswer,
    SecurityAssessment,
)
from app.models.edge import DeploymentTask, EdgeNode, FederatedJob, FederatedRound
from app.models.job import (
    JOB_STATUSES,
    JOB_TYPES,
    TERMINAL_STATUSES,
    AsyncJob,
    AsyncJobEvent,
)
from app.models.evaluation import (
    EvalDataset,
    EvalDatasetItem,
    EvalMetric,
    EvalRocPoint,
    EvalRun,
    MrMcComparison,
)
from app.models.label import (
    LABEL_LAYER_LABELS,
    LABEL_LAYERS,
    Annotation,
    AnnotatorProfile,
    Arbitration,
    LabelSchema,
    LabelSop,
    QcRecord,
)
from app.models.modeling import (
    ComputeResource,
    EncoderRegistry,
    LoraAdapter,
    ModelBase,
    ModelVersion,
    TrainingJob,
)
from app.models.ops import CostStructure, KpiSnapshot, RevenuePath, StrategicDecision, TeamRole
from app.models.pipeline import AttentionRegion, CaseEmbedding, InferenceJob, SlidePrediction
from app.models.registry import (
    REGISTRATION_STAGES,
    ClinicalTrialSite,
    GuidelineDoc,
    RegistrationMilestone,
    RegistrationPath,
    RegistrationStage,
    RiskItem,
)
from app.models.system import (
    Dictionary,
    LoginAttempt,
    RefreshSession,
    RoleModel,
    SystemConfig,
    User,
    user_roles,
)

__all__ = [
    # base
    "BaseModel", "TimestampMixin", "CodeNameMixin", "utcnow",
    # system
    "User", "RoleModel", "user_roles", "SystemConfig", "Dictionary",
    "RefreshSession", "LoginAttempt",
    # asset
    "DataAsset", "Slide", "SlideFeature", "StorageStat", "AssetExtension",
    # label
    "LABEL_LAYERS", "LABEL_LAYER_LABELS",
    "LabelSchema", "AnnotatorProfile", "LabelSop", "Annotation", "QcRecord", "Arbitration",
    # modeling
    "EncoderRegistry", "ModelBase", "ModelVersion", "TrainingJob", "LoraAdapter", "ComputeResource",
    # pipeline
    "InferenceJob", "SlidePrediction", "AttentionRegion", "CaseEmbedding",
    # agent
    "AGENT_ROLES", "AGENT_ROLE_LABELS", "MAGNIFICATION_LADDER",
    "AgentCapability", "AgentSession", "AgentStep", "AgentProbe",
    "AgentEvidence", "AgentDiagnosis", "AgentVote", "ReviewTicket",
    # evaluation
    "EvalDataset", "EvalDatasetItem", "EvalRun", "EvalRocPoint", "EvalMetric", "MrMcComparison",
    # compliance
    "REVIEW_GROUPS", "REVIEW_GROUP_LABELS",
    "EthicsRecord", "ConsentRecord", "AuditChainRecord", "DataBoundaryCheck",
    "SecurityAssessment", "ExplainabilityPackage", "ReviewQuestionAnswer", "ChangeRegistration",
    # edge
    "EdgeNode", "FederatedJob", "FederatedRound", "DeploymentTask",
    # registry
    "REGISTRATION_STAGES", "RegistrationPath", "RegistrationStage",
    "RegistrationMilestone", "RiskItem", "ClinicalTrialSite", "GuidelineDoc",
    # ops
    "TeamRole", "CostStructure", "RevenuePath", "KpiSnapshot", "StrategicDecision",
    # job
    "JOB_TYPES", "JOB_STATUSES", "TERMINAL_STATUSES", "AsyncJob", "AsyncJobEvent",
]
