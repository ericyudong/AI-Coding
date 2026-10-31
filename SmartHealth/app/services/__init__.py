"""业务服务层。

分层约定：
- `image_utils` / `wsi_service` / `encoder_service` / `mil_service` / `evaluation_service`
  —— 算法底座，纯计算，不依赖数据库会话。
- `pipeline_service` / `agent_service` / `label_service` / `compliance_service`
  / `edge_service` / `registry_service` / `ops_service`
  —— 业务编排，接收 SQLAlchemy Session，负责落库与审计链写入。
"""

from app.services.encoder_service import encoder_service
from app.services.evaluation_service import full_report
from app.services.mil_service import GatedABMIL, MilConfig

__all__ = ["encoder_service", "GatedABMIL", "MilConfig", "full_report"]
