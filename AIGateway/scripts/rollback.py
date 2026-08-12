"""
一键回退：改镜像标签 / 切路由权重，满足 MTTR ≤ 15 min。

用法:
  # 把 default 流量切到 local（合规降级）
  python scripts/rollback.py --mode route --target local

  # 回退 Kustomize 镜像标签到上一版本
  python scripts/rollback.py --mode image --tag abc12345

  # 恢复 fallbacks 金丝雀权重（dev 配置示例）
  python scripts/rollback.py --mode weight --canary-weight 0
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _backup(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_suffix(path.suffix + f".bak.{ts}")
    shutil.copy2(path, bak)
    print(f"backup → {bak}")
    return bak


def rollback_route(config_path: Path, target: str) -> None:
    """将所有虚拟模型的主路由临时改写为 target（如 local）。"""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    _backup(config_path)

    # 在 general_settings 记一笔审计
    data.setdefault("general_settings", {})
    data["general_settings"]["rollback"] = {
        "mode": "route",
        "target": target,
        "at": datetime.now(timezone.utc).isoformat(),
    }

    # 强制 fallbacks：任何模型失败都落到 target；并加别名强制
    data["router_settings"] = data.get("router_settings") or {}
    model_names = sorted(
        {m["model_name"] for m in data.get("model_list") or [] if "model_name" in m}
    )
    data["router_settings"]["fallbacks"] = [[name, target] for name in model_names if name != target]

    # 写入强制路由注解文件，供运维确认
    note = ROOT / "reports" / "rollback_route.json"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        json.dumps(
            {
                "action": "route_fallback_to",
                "target": target,
                "config": str(config_path),
                "hint": f"业务方也可直接把 model 设为 '{target}'；或设 header x-model-tier: local",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    config_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Updated fallbacks → {target} in {config_path}")


def rollback_image(kustomization: Path, tag: str, image_name: str) -> None:
    """kustomize edit set image 等价操作：改 patch-image / kustomization images。"""
    _backup(kustomization)
    data = yaml.safe_load(kustomization.read_text(encoding="utf-8")) or {}
    images: List[Dict[str, Any]] = data.get("images") or []
    found = False
    for img in images:
        if img.get("name") == image_name or image_name in str(img.get("name", "")):
            img["newTag"] = tag
            found = True
    if not found:
        images.append({"name": image_name, "newTag": tag})
        data["images"] = images
    kustomization.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Set {image_name} newTag={tag} in {kustomization}")
    print("提示: git commit + push 后由 Argo CD reconcile；或本地 kubectl apply -k ...")


def rollback_weight(config_path: Path, canary_weight: float) -> None:
    """把 load_balancing_weights 金丝雀权重压到 canary_weight（0=关掉金丝雀）。"""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    _backup(config_path)
    rs = data.setdefault("router_settings", {})
    weights = rs.setdefault("load_balancing_weights", {})
    # 约定：default 组内 gpt-4o 为稳定版，azure/gpt-4o 为金丝雀时可压权重
    weights["default"] = {"gpt-4o": 1.0 - canary_weight, "azure/gpt-4o": canary_weight}
    rs["load_balancing_weights"] = weights
    data["general_settings"] = data.get("general_settings") or {}
    data["general_settings"]["rollback"] = {
        "mode": "weight",
        "canary_weight": canary_weight,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    config_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Canary weight set to {canary_weight} in {config_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Gateway rollback helper")
    parser.add_argument("--mode", choices=["route", "image", "weight"], required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "config.yaml")
    parser.add_argument("--target", default="local", help="route 模式目标模型")
    parser.add_argument("--tag", help="image 模式镜像标签")
    parser.add_argument(
        "--kustomization",
        type=Path,
        default=ROOT / "deployments" / "k8s" / "envs" / "prod" / "kustomization.yaml",
    )
    parser.add_argument(
        "--image-name",
        default="registry.internal.example.com/ai/ai-gateway",
    )
    parser.add_argument("--canary-weight", type=float, default=0.0)
    args = parser.parse_args()

    if args.mode == "route":
        rollback_route(args.config, args.target)
    elif args.mode == "image":
        if not args.tag:
            print("ERROR: --mode image 需要 --tag", file=sys.stderr)
            return 2
        rollback_image(args.kustomization, args.tag, args.image_name)
    elif args.mode == "weight":
        rollback_weight(args.config, args.canary_weight)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
