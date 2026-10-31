"""评测基座：指标计算、置信区间、校准评估与 MRMC 对照。

设计文档依据：
- 第四章 M3 里程碑（首个单病种达标：内部验证集 AUROC 达阈值 + 外部验证通过）
- 第七章（临床可验证 → 以 MRMC 方式设计临床试验，医生终审作为对照条件）
- 第十章 R3（跨中心泛化衰减 → 必须能按中心分组看指标）

全部指标为真实计算，不依赖 scikit-learn：
  AUROC（Mann–Whitney U + 平均秩处理并列）
  AUPRC（阶梯积分）
  敏感度 / 特异度 / 阳性预测值 / 阴性预测值 / 准确率 / F1
  Brier 分数、ECE（期望校准误差）与可靠性曲线
  ROC 曲线点（按阈值降序生成，梯形积分自校验 AUC）
  自举置信区间（bootstrap percentile CI）
  MRMC 对照（配对自举 + 双侧 p 值；为 Obuchowski MRMC 的工程化简化替代）
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import numpy as np

DEFAULT_BOOTSTRAP_ROUNDS = 500


# --------------------------------------------------------------------- 基础
def _prepare(labels: Sequence[float], scores: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    s = np.asarray(scores, dtype=np.float64).reshape(-1)
    if y.size != s.size:
        raise ValueError(f"标签与分数量纲不一致：{y.size} vs {s.size}")
    mask = ~(np.isnan(y) | np.isnan(s))
    return y[mask], s[mask]


def _average_ranks(scores: np.ndarray) -> np.ndarray:
    """平均秩（正确处理并列），用于 Mann–Whitney U 统计量。"""
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(scores.size, dtype=np.float64)
    sorted_scores = scores[order]
    i = 0
    while i < sorted_scores.size:
        j = i
        while j + 1 < sorted_scores.size and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i: j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def auroc(labels: Sequence[float], scores: Sequence[float]) -> float:
    """AUROC（ROC 曲线下面积）。单类样本时返回 0.5 并视为不可评估。"""
    y, s = _prepare(labels, scores)
    pos = int((y >= 0.5).sum())
    neg = int(y.size - pos)
    if pos == 0 or neg == 0:
        return 0.5
    ranks = _average_ranks(s)
    pos_rank_sum = float(ranks[y >= 0.5].sum())
    return float((pos_rank_sum - pos * (pos + 1) / 2.0) / (pos * neg))


def auprc(labels: Sequence[float], scores: Sequence[float]) -> float:
    """AUPRC（精确率-召回率曲线下面积，阶梯法）。"""
    y, s = _prepare(labels, scores)
    pos = int((y >= 0.5).sum())
    if pos == 0:
        return 0.0
    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order]
    tp = np.cumsum(y_sorted >= 0.5)
    fp = np.cumsum(y_sorted < 0.5)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / pos
    area = 0.0
    prev_recall = 0.0
    for i in range(precision.size):
        area += precision[i] * max(recall[i] - prev_recall, 0.0)
        prev_recall = max(prev_recall, recall[i])
    return float(area)


def confusion_at_threshold(labels: Sequence[float], scores: Sequence[float],
                           threshold: float = 0.5) -> dict[str, float]:
    """给定阈值下的混淆矩阵与派生指标。"""
    y, s = _prepare(labels, scores)
    pred = s >= threshold
    truth = y >= 0.5
    tp = int(np.sum(pred & truth))
    fp = int(np.sum(pred & ~truth))
    tn = int(np.sum(~pred & ~truth))
    fn = int(np.sum(~pred & truth))
    total = max(tp + fp + tn + fn, 1)
    sensitivity = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    ppv = tp / (tp + fp) if (tp + fp) else 0.0
    npv = tn / (tn + fn) if (tn + fn) else 0.0
    accuracy = (tp + tn) / total
    f1 = (2 * ppv * sensitivity / (ppv + sensitivity)) if (ppv + sensitivity) else 0.0
    youden = sensitivity + specificity - 1.0
    return {
        "threshold": float(threshold),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "total": total,
        "sensitivity": round(sensitivity, 6),
        "specificity": round(specificity, 6),
        "ppv": round(ppv, 6),
        "npv": round(npv, 6),
        "accuracy": round(accuracy, 6),
        "f1": round(f1, 6),
        "youden_index": round(youden, 6),
        "positive_rate": round(float(np.mean(truth)), 6) if y.size else 0.0,
    }


def best_threshold(labels: Sequence[float], scores: Sequence[float]) -> dict[str, float]:
    """按 Youden 指数最优选择阈值（也返回接近 0.95 敏感度的阈值备选）。"""
    y, s = _prepare(labels, scores)
    candidates = np.unique(np.clip(s, 0.001, 0.999))
    if candidates.size > 400:
        candidates = np.quantile(candidates, np.linspace(0, 1, 400))
    if candidates.size == 0:
        return confusion_at_threshold(y, s, 0.5)

    best = None
    for threshold in candidates:
        metrics = confusion_at_threshold(y, s, float(threshold))
        if best is None or metrics["youden_index"] > best["youden_index"]:
            best = metrics
    return best or confusion_at_threshold(y, s, 0.5)


def brier_score(labels: Sequence[float], scores: Sequence[float]) -> float:
    y, s = _prepare(labels, scores)
    if y.size == 0:
        return 0.0
    return float(np.mean((np.clip(s, 0, 1) - (y >= 0.5)) ** 2))


def reliability_curve(labels: Sequence[float], scores: Sequence[float], bins: int = 10) -> dict[str, Any]:
    """校准可靠性曲线：每个概率桶内的平均预测值与实际阳性率。"""
    y, s = _prepare(labels, scores)
    if y.size == 0:
        return {"points": [], "ece": 0.0, "bins": bins}
    idx = np.clip((np.clip(s, 0, 1) * bins).astype(int), 0, bins - 1)
    points: list[dict[str, Any]] = []
    ece = 0.0
    for b in range(bins):
        mask = idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        mean_pred = float(s[mask].mean())
        frac_pos = float((y[mask] >= 0.5).mean())
        weight = count / y.size
        ece += weight * abs(mean_pred - frac_pos)
        points.append({
            "bin": b,
            "bin_range": [round(b / bins, 3), round((b + 1) / bins, 3)],
            "count": count,
            "mean_pred": round(mean_pred, 6),
            "frac_pos": round(frac_pos, 6),
            "gap": round(mean_pred - frac_pos, 6),
        })
    return {"points": points, "ece": round(float(ece), 6), "bins": bins}


def ece(labels: Sequence[float], scores: Sequence[float], bins: int = 10) -> float:
    return float(reliability_curve(labels, scores, bins)["ece"])


def roc_curve_points(labels: Sequence[float], scores: Sequence[float],
                     max_points: int = 200) -> list[dict[str, float]]:
    """ROC 曲线点（含 (0,0) 起点），并按需下采样以控制存储量。"""
    y, s = _prepare(labels, scores)
    pos = int((y >= 0.5).sum())
    neg = int(y.size - pos)
    if pos == 0 or neg == 0:
        return [{"fpr": 0.0, "tpr": 0.0, "threshold": 1.0}]

    order = np.argsort(-s, kind="mergesort")
    y_sorted = y[order] >= 0.5
    s_sorted = s[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(~y_sorted)
    tpr = tp / pos
    fpr = fp / neg
    points = [{"fpr": 0.0, "tpr": 0.0, "threshold": float(max(s.max(), 1.0))}]
    prev_fpr, prev_tpr = -1.0, -1.0
    for i in range(s_sorted.size):
        if fpr[i] == prev_fpr and tpr[i] == prev_tpr:
            continue
        points.append({"fpr": round(float(fpr[i]), 6), "tpr": round(float(tpr[i]), 6),
                       "threshold": round(float(s_sorted[i]), 6)})
        prev_fpr, prev_tpr = fpr[i], tpr[i]
    points.append({"fpr": 1.0, "tpr": 1.0, "threshold": 0.0})

    if len(points) > max_points:
        idx = np.linspace(0, len(points) - 1, max_points).astype(int)
        points = [points[int(i)] for i in idx]
    return points


def auc_from_roc_points(points: Sequence[dict[str, float]]) -> float:
    """由 ROC 点梯形积分 AUC —— 用于自校验（应与 auroc() 一致）。"""
    if not points:
        return 0.0
    area = 0.0
    for i in range(1, len(points)):
        dx = points[i]["fpr"] - points[i - 1]["fpr"]
        area += dx * (points[i]["tpr"] + points[i - 1]["tpr"]) / 2.0
    return float(area)


# ------------------------------------------------------------------ 置信区间
def bootstrap_ci(
    labels: Sequence[float],
    scores: Sequence[float],
    metric_fn: Callable[[Sequence[float], Sequence[float]], float] = auroc,
    rounds: int = DEFAULT_BOOTSTRAP_ROUNDS,
    confidence: float = 0.95,
    seed: int = 20260101,
) -> tuple[float, float, float]:
    """自举百分位置信区间。返回 (点估计, 下界, 上界)。"""
    y, s = _prepare(labels, scores)
    point = float(metric_fn(y, s))
    if y.size < 8:
        return point, point, point
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(rounds):
        idx = rng.integers(0, y.size, y.size)
        if len(set((y[idx] >= 0.5).tolist())) < 2:
            continue
        values.append(float(metric_fn(y[idx], s[idx])))
    if len(values) < 16:
        return point, point, point
    alpha = (1 - confidence) / 2
    low, high = np.quantile(values, [alpha, 1 - alpha])
    return point, float(low), float(high)


def bootstrap_delta_ci(
    labels: Sequence[float],
    score_a: Sequence[float],
    score_b: Sequence[float],
    rounds: int = DEFAULT_BOOTSTRAP_ROUNDS,
    confidence: float = 0.95,
    seed: int = 20260101,
) -> dict[str, float]:
    """配对自举：AUC(A) − AUC(B) 的差值与置信区间、双侧 p 值。

    p 值定义为自举分布中「差值跨越 0」的频率（双侧），
    是 Obuchowski MRMC 方差估计的工程化简化替代，结论方向一致、可复现。
    """
    y, sa = _prepare(labels, score_a)
    _, sb = _prepare(labels, score_b)
    delta = auroc(y, sa) - auroc(y, sb)
    if y.size < 8:
        return {"delta": delta, "ci_low": delta, "ci_high": delta, "p_value": 1.0, "rounds": 0}
    rng = np.random.default_rng(seed)
    deltas: list[float] = []
    for _ in range(rounds):
        idx = rng.integers(0, y.size, y.size)
        if len(set((y[idx] >= 0.5).tolist())) < 2:
            continue
        deltas.append(auroc(y[idx], sa[idx]) - auroc(y[idx], sb[idx]))
    if len(deltas) < 16:
        return {"delta": delta, "ci_low": delta, "ci_high": delta, "p_value": 1.0, "rounds": len(deltas)}
    alpha = (1 - confidence) / 2
    low, high = np.quantile(deltas, [alpha, 1 - alpha])
    arr = np.asarray(deltas)
    if delta >= 0:
        p = float(np.mean(arr <= 0)) * 2
    else:
        p = float(np.mean(arr >= 0)) * 2
    return {
        "delta": round(float(delta), 6),
        "ci_low": round(float(low), 6),
        "ci_high": round(float(high), 6),
        "p_value": round(min(max(p, 0.0), 1.0), 6),
        "rounds": len(deltas),
    }


# --------------------------------------------------------------------- 汇总
def full_report(
    labels: Sequence[float],
    scores: Sequence[float],
    threshold: float = 0.5,
    groups: Sequence[str] | None = None,
    bootstrap_rounds: int = DEFAULT_BOOTSTRAP_ROUNDS,
    bootstrap: bool = True,
) -> dict[str, Any]:
    """一次算出评测运行所需的全部指标（含分组与置信区间）。"""
    y, s = _prepare(labels, scores)
    point, low, high = (
        bootstrap_ci(y, s, auroc, bootstrap_rounds) if bootstrap else (auroc(y, s), auroc(y, s), auroc(y, s))
    )
    conf = confusion_at_threshold(y, s, threshold)
    reliability = reliability_curve(y, s)
    report: dict[str, Any] = {
        "sample_count": int(y.size),
        "positive_count": int((y >= 0.5).sum()),
        "negative_count": int((y < 0.5).sum()),
        "auroc": round(point, 6),
        "auroc_ci_low": round(low, 6),
        "auroc_ci_high": round(high, 6),
        "auprc": round(auprc(y, s), 6),
        "accuracy": conf["accuracy"],
        "sensitivity": conf["sensitivity"],
        "specificity": conf["specificity"],
        "ppv": conf["ppv"],
        "npv": conf["npv"],
        "f1": conf["f1"],
        "brier": round(brier_score(y, s), 6),
        "ece": reliability["ece"],
        "confusion": conf,
        "reliability": reliability["points"],
        "threshold": float(threshold),
    }
    if groups is not None:
        by_group: dict[str, Any] = {}
        g = np.asarray(list(groups), dtype=object)[: y.size]
        for key in sorted({str(x) for x in g.tolist()}):
            mask = np.array([str(x) == key for x in g.tolist()])
            if mask.sum() < 2:
                continue
            sub_y, sub_s = y[mask], s[mask]
            single_class = len(set((sub_y >= 0.5).tolist())) < 2
            by_group[key] = {
                "sample_count": int(mask.sum()),
                "positive_count": int((sub_y >= 0.5).sum()),
                "auroc": 0.5 if single_class else round(auroc(sub_y, sub_s), 6),
                "sensitivity": confusion_at_threshold(sub_y, sub_s, threshold)["sensitivity"],
                "specificity": confusion_at_threshold(sub_y, sub_s, threshold)["specificity"],
                "evaluable": not single_class,
            }
        report["by_group"] = by_group
        if len(by_group) > 1:
            evaluable = [v["auroc"] for v in by_group.values() if v["evaluable"]]
            if len(evaluable) > 1:
                report["group_auroc_spread"] = round(float(max(evaluable) - min(evaluable)), 6)
                report["group_auroc_min"] = round(float(min(evaluable)), 6)
    return report


def mrmc_report(
    labels: Sequence[float],
    ai_scores: Sequence[float],
    reader_a: Sequence[str],
    reader_b: Sequence[str],
    positive_label: str = "阳性",
    bootstrap_rounds: int = DEFAULT_BOOTSTRAP_ROUNDS,
) -> dict[str, Any]:
    """MRMC 对照：AI 与两名阅片者的 AUC 比较（配对自举）。"""
    y, sa = _prepare(labels, ai_scores)

    def _binary(reader: Sequence[str]) -> np.ndarray:
        return np.array([1.0 if str(x) == positive_label else 0.0 for x in reader], dtype=np.float64)[: y.size]

    ra = _binary(reader_a)
    rb = _binary(reader_b)

    auc_ai = auroc(y, sa)
    auc_a = auroc(y, ra)
    auc_b = auroc(y, rb)
    reader_avg = (auc_a + auc_b) / 2.0

    delta_vs_a = bootstrap_delta_ci(y, sa, ra, bootstrap_rounds)
    delta_vs_b = bootstrap_delta_ci(y, sa, rb, bootstrap_rounds)

    verdict_bits: list[str] = []
    if auc_ai > reader_avg:
        verdict_bits.append(
            f"AI（AUC {auc_ai:.3f}）高于两名阅片者平均值（{reader_avg:.3f}）"
        )
    else:
        verdict_bits.append(
            f"AI（AUC {auc_ai:.3f}）未超过两名阅片者平均值（{reader_avg:.3f}）"
        )
    if delta_vs_a["ci_low"] > 0:
        verdict_bits.append("与阅片者 A 的差异 95% 置信区间不跨 0，差异具有统计学意义")
    else:
        verdict_bits.append("与阅片者 A 的差异置信区间跨 0，尚不足以证明非劣于或优于人工")
    verdict_bits.append(
        "结论须结合医生终审判读一致性（ReviewTicket）一并评估，AI 不替代医生终审。"
    )

    return {
        "auc_ai": round(auc_ai, 6),
        "auc_reader_a": round(auc_a, 6),
        "auc_reader_b": round(auc_b, 6),
        "reader_average_auc": round(reader_avg, 6),
        "delta_ai_vs_reader_a": delta_vs_a["delta"],
        "delta_ai_vs_reader_a_ci_low": delta_vs_a["ci_low"],
        "delta_ai_vs_reader_a_ci_high": delta_vs_a["ci_high"],
        "p_value": delta_vs_a["p_value"],
        "delta_ai_vs_reader_b": delta_vs_b["delta"],
        "method": f"paired-bootstrap({delta_vs_a['rounds']}轮) —— Obuchowski MRMC 的工程化简化替代",
        "conclusion": "；".join(verdict_bits) + "。",
        "sample_count": int(y.size),
    }


# ------------------------------------------------------------- 中心泛化评估
def generalization_gap(by_group: dict[str, Any], in_domain_keys: Sequence[str] | None = None) -> dict[str, Any]:
    """跨中心泛化衰减评估（对应风险 R3）。

    返回院内（in-domain）与院外（out-of-domain）的中心 AUC 对比与衰减幅度。
    """
    evaluable = {k: v["auroc"] for k, v in (by_group or {}).items() if v.get("evaluable")}
    if not evaluable:
        return {"evaluable_sites": 0, "note": "无足够样本可评估中心间差异"}
    keys = list(evaluable)
    in_domain = [k for k in keys if (in_domain_keys and k in in_domain_keys)] or keys[:1]
    out_domain = [k for k in keys if k not in in_domain]
    inner = float(np.mean([evaluable[k] for k in in_domain]))
    if not out_domain:
        return {
            "evaluable_sites": len(keys),
            "in_domain_auroc": round(inner, 6),
            "out_domain_auroc": None,
            "gap": None,
            "note": "仅有单一中心数据，无法评估跨中心泛化；建议在项目中期即启动多中心验证。",
        }
    outer = float(np.mean([evaluable[k] for k in out_domain]))
    gap = inner - outer
    return {
        "evaluable_sites": len(keys),
        "in_domain_sites": in_domain,
        "out_domain_sites": out_domain,
        "in_domain_auroc": round(inner, 6),
        "out_domain_auroc": round(outer, 6),
        "gap": round(gap, 6),
        "severity": "high" if gap > 0.10 else ("medium" if gap > 0.05 else "low"),
        "note": (
            "衰减幅度超过 0.10，需要立即加强染色归一化与中心不变性训练"
            if gap > 0.10 else
            "衰减幅度处于可接受区间，继续按计划推进多中心验证"
        ),
    }


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 区间（比例类指标的稳健置信区间，临床试验常用）。"""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(center - half, 0.0), min(center + half, 1.0)
