"""模型仓库 CLI：清单 / 安装 / 校验 / 卸载 / 导出自研参照模型。

    # 列出清单（含许可、安装状态、校验和）
    python scripts/model_registry.py list

    # 同步内置编码器声明到清单（幂等，不覆盖已装记录）
    python scripts/model_registry.py sync

    # 导出自研参照模型（真实 ONNX 计算图，用于验证推理链路）
    python scripts/model_registry.py export-reference --dim 256

    # 安装权重：院内离线用 --from 本地文件；有外网时按清单 source_url 下载
    python scripts/model_registry.py install hibou-b-onnx --from D:/weights/hibou-b.onnx

    # 校验（文件存在 + SHA256 + ONNX 结构 + 维度一致性）
    python scripts/model_registry.py verify hibou-b-onnx
    python scripts/model_registry.py verify --all

    # 卸载
    python scripts/model_registry.py uninstall hibou-b-onnx

    # 许可体检：哪些能用于商用主线、哪些只在探索线
    python scripts/model_registry.py license-audit

退出码：0 成功；1 失败（校验失败 / 许可拦截 / 参数错误）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _print_overview(overview: dict) -> None:
    print("=" * 92)
    print("  模型权重清单")
    print("=" * 92)
    print(f"  清单：{overview['manifest_path']}    权重目录：{overview['models_dir']}/")
    print(f"  合计 {overview['total']} 条 · 已安装 {overview['installed']} · "
          f"可商用且已安装 {overview['commercial_ready']} · "
          f"自研 {overview['self_developed']} · 环境 {overview['env']}")
    print(f"  按阶段：{overview['by_stage']}")
    print(f"  按许可：{overview['by_license']}")
    print("-" * 92)
    header = f"  {'编码':<20}{'维度':>5}{'尺寸':>6}  {'可商用':<7}{'阶段':<10}{'安排':<6}{'许可':<20}"
    print(header)
    print("-" * 92)
    for m in overview["models"]:
        installed = "已装" if m["exists"] else "—"
        print(f"  {m['code']:<20}{m['embedding_dim']:>5}{m['tile_size']:>6}  "
              f"{('是' if m['commercial_usable'] else '否'):<7}{m['stage']:<10}"
              f"{installed:<6}{(m['license_code'] or '未标注'):<20}")
    print("=" * 92)


def _print_verify(result: dict) -> None:
    icon = {True: "[ OK ]", False: "[FAIL]"}
    print(f"\n校验 {result['code']}：{'通过' if result['ok'] else '未通过'}")
    for check in result.get("checks", []):
        print(f"  {icon[bool(check['ok'])]} {check['name']:<34} {check['detail']}")
    if result.get("error"):
        print(f"  → {result['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartHealth 模型仓库")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出清单")

    sub.add_parser("sync", help="把内置编码器声明同步进清单（幂等）")

    p_export = sub.add_parser("export-reference", help="导出自研参照 ONNX 模型")
    p_export.add_argument("--code", default="sh-ref-cnn-v1")
    p_export.add_argument("--dim", type=int, default=256, help="embedding 维度")
    p_export.add_argument("--tile", type=int, default=128, help="输入边长")
    p_export.add_argument("--seed", type=int, default=20261030)
    p_export.add_argument("--static-batch", action="store_true",
                          help="导出为静态 batch=1（默认动态 batch）")

    p_install = sub.add_parser("install", help="安装权重")
    p_install.add_argument("code")
    p_install.add_argument("--from", dest="source", default="", help="本地权重文件路径")
    p_install.add_argument("--env", default="", help="部署环境 research/product")
    p_install.add_argument("--stage", default="", help="安装后标记的阶段")
    p_install.add_argument("--sha256", default="", help="期望的 SHA256（覆盖清单值）")
    p_install.add_argument("--actor", default="", help="操作人（写入清单）")
    p_install.add_argument("--force-license", action="store_true",
                           help="跳过许可门禁（**仅限科研环境**，会写入清单备注）")

    p_verify = sub.add_parser("verify", help="校验权重")
    p_verify.add_argument("code", nargs="?", default="")
    p_verify.add_argument("--all", action="store_true")

    p_uninstall = sub.add_parser("uninstall", help="卸载权重")
    p_uninstall.add_argument("code")

    sub.add_parser("license-audit", help="许可体检（哪些能进商用主线）")

    p_json = sub.add_parser("overview-json", help="以 JSON 输出清单概览")
    p_json.add_argument("--pretty", action="store_true")

    args = parser.parse_args()

    from app.services import model_registry as reg

    if args.command == "list":
        _print_overview(reg.registry_overview())
        return 0

    if args.command == "sync":
        added = reg.seeded_default_manifest()
        print(f"已同步：新增 {added} 条（已存在的记录保持不变）")
        return 0

    if args.command == "export-reference":
        result = reg.export_reference_model(
            code=args.code, embedding_dim=args.dim, tile_size=args.tile,
            seed=args.seed, dynamic_batch=not args.static_batch)
        entry = reg.register_reference(code=args.code, embedding_dim=args.dim,
                                       tile_size=args.tile, seed=args.seed)
        print("=" * 92)
        print("  已导出自研参照 ONNX 模型并登记进清单")
        print("=" * 92)
        print(f"  文件：{result['path']}（{result['bytes'] / 1024:.1f} KB）")
        print(f"  SHA256：{result['sha256']}")
        print(f"  结构：{result['nodes']} 个节点 · {result['params']:,} 参数 "
              f"（{result['params_m']} M）")
        print(f"  输入：1×3×{result['tile_size']}×{result['tile_size']}   "
              f"输出：{result['embedding_dim']} 维")
        print(f"  下采样：{result['downsample_factor']}× "
              f"（{result['channels']} 个卷积块，末层特征图 {result['feature_map_at_input']}×"
              f"{result['feature_map_at_input']}）")
        print(f"  动态 batch：{result['dynamic_batch']}")
        print()
        print("  说明：这是真实可执行的 ONNX 计算图（真实卷积与张量），用于验证推理链路与")
        print("        权重治理；它不是病理预训练权重，其指标不代表模型性能。")
        print("=" * 92)
        return 0

    if args.command == "install":
        try:
            entry = reg.install_entry(
                args.code, source=args.source, deployment_env=args.env,
                stage=args.stage, actor=args.actor, expect_sha256=args.sha256,
                allow_license_override=args.force_license)
        except reg.LicenseDenied as exc:
            print("[FAIL] 许可门禁拦截（未安装任何文件）\n")
            print(str(exc))
            return 1
        except reg.ModelRegistryError as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"已安装 {entry.code} → {entry.installed_path}"
              f"（{entry.bytes / 1024 / 1024:.2f} MB）")
        print(f"  SHA256：{entry.installed_sha256}")
        return 0

    if args.command == "verify":
        if args.all or not args.code:
            summary = reg.verify_all()
            for result in summary["results"]:
                _print_verify(result)
            print("\n" + "=" * 92)
            print(f"  校验合计：{summary['ok']}/{summary['total']} 通过"
                  + (f" · 未通过：{', '.join(summary['failed'])}" if summary["failed"] else ""))
            print("=" * 92)
            return 0 if not summary["failed"] else 1
        result = reg.verify_entry(args.code)
        _print_verify(result)
        return 0 if result["ok"] else 1

    if args.command == "uninstall":
        try:
            info = reg.uninstall_entry(args.code)
        except reg.ModelRegistryError as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"已卸载 {info['code']}"
              + (f"，删除文件 {info['removed_file']}" if info["removed_file"] else "（无文件可删）"))
        return 0

    if args.command == "license-audit":
        overview = reg.registry_overview()
        allowed, blocked, unlicensed = [], [], []
        for m in overview["models"]:
            if not m["license_code"]:
                unlicensed.append(m)
            elif m["commercial_usable"]:
                allowed.append(m)
            else:
                blocked.append(m)
        print("=" * 92)
        print("  许可体检（能否进入商用主线）")
        print("=" * 92)
        print(f"\n[可商用] {len(allowed)} 项")
        for m in allowed:
            print(f"  · {m['code']:<22}{m['license_name']:<28}"
                  f"{'已安装' if m['exists'] else '未安装'}")
        print(f"\n[仅限科研/探索线] {len(blocked)} 项 —— 不可用于申报 NMPA 三类证的产品")
        for m in blocked:
            print(f"  · {m['code']:<22}{m['license_name']:<28}{m['license_note'][:44]}")
        if unlicensed:
            print(f"\n[未标注许可] {len(unlicensed)} 项 —— 必须先补齐许可信息")
            for m in unlicensed:
                print(f"  · {m['code']}")
        print("\n" + "=" * 92)
        print("  结论：商用主线只能使用上表「可商用」项。在 product 环境下安装非商用权重")
        print("        会被 install 命令直接拒绝 —— 把合规约束前置到安装动作，而不是等注册。")
        print("=" * 92)
        return 0

    if args.command == "overview-json":
        data = reg.registry_overview()
        print(json.dumps(data, ensure_ascii=False,
                         indent=2 if args.pretty else None))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
