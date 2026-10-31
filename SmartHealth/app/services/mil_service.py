"""ABMIL 切片级聚合（注意力门控多示例学习）。

设计文档依据：第四章 4.4「图块级特征模型 + 切片级聚合」，这是**唯一已被证明
可通过器械注册的技术路线**（有临床验证证据与获批先例）。

算法：Ilse et al. 2018 的 Gated Attention MIL，纯 numpy 前向 + 手写反向传播 + Adam。
- 输入：一张切片的 N 个图块嵌入 (N, D)
- 输出：切片级概率 p，以及**每个图块的注意力权重 A**（ΣA=1）

注意力权重在本方案里承担三重角色，不是装饰：
1. 可解释性（注册审评「问二 算法可解释」）—— 定位到具体区域的证据；
2. Agent 导航的候选区域池（第五章）—— 注意力高的区域优先升级到高倍确认；
3. 证据强制引用的底层数据（AgentEvidence.attention_region）。

同时实现 Platt 标定（`PlattScaler`），把模型原始 logit 映射为**校准后概率**，
这是「置信度分级」与「拒识」机制能否成立的前提。
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- 工具
def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))


def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return x
    shifted = x - np.max(x)
    exp = np.exp(shifted)
    total = exp.sum()
    return exp / total if total > 0 else np.full_like(exp, 1.0 / exp.size)


def binary_cross_entropy(prob: float, label: float, pos_weight: float = 1.0) -> float:
    eps = 1e-9
    p = min(max(prob, eps), 1 - eps)
    weight = pos_weight if label >= 0.5 else 1.0
    return float(-weight * (label * math.log(p) + (1 - label) * math.log(1 - p)))


# --------------------------------------------------------------------- 配置
@dataclass
class MilConfig:
    in_dim: int = 128
    attn_dim: int = 128
    l2_reg: float = 1e-4
    epochs: int = 160
    learning_rate: float = 0.02
    seed: int = 20260101
    pos_weight: float = 1.0
    early_stop_patience: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- Platt 标定
class PlattScaler:
    """把 logit 映射为校准概率：p = sigmoid(a·logit + b)。

    实现要点（否则在近似可分的样本上 Newton 迭代会发散）：
    1. 先对 logit 做 z-score 标准化再拟合 —— 条件数从 1e4 量级降到 1 量级；
    2. 每步 Newton 更新做步长裁剪，避免越过极值点；
    3. 拟合后与「不做标定」的 Brier 分数对比，变差就自动回退到恒等映射。

    标定质量用 ECE（期望校准误差）衡量，见 evaluation_service。
    """

    def __init__(self) -> None:
        self.a = 1.0
        self.b = 0.0
        self.fitted = False
        self.iterations = 0
        self.reason = "未拟合"
        self.z_mean = 0.0
        self.z_scale = 1.0

    def _transform_raw(self, a: float, b: float, z: np.ndarray) -> np.ndarray:
        return sigmoid(a * z + b)

    @staticmethod
    def _brier(labels: np.ndarray, probs: np.ndarray) -> float:
        return float(np.mean((np.clip(probs, 0, 1) - labels) ** 2))

    def fit(self, logits: Sequence[float], labels: Sequence[float], ridge: float = 1e-2,
            max_iter: int = 80, max_step: float = 1.0) -> "PlattScaler":
        z = np.asarray(logits, dtype=np.float64).reshape(-1)
        y = np.asarray(labels, dtype=np.float64).reshape(-1)
        if z.size < 8 or len(set(y.tolist())) < 2:
            self.fitted = False
            self.reason = "样本不足或单一类别，跳过标定（退化为原始 sigmoid）"
            return self

        z_mean = float(z.mean())
        z_scale = float(z.std())
        if not np.isfinite(z_scale) or z_scale < 1e-6:
            self.fitted = False
            self.reason = "logit 方差过小，跳过标定"
            return self
        zs = (z - z_mean) / z_scale
        self.z_mean, self.z_scale = z_mean, z_scale

        a, b = 1.0, 0.0
        for step in range(max_iter):
            p = sigmoid(a * zs + b)
            w = np.clip(p * (1 - p), 1e-9, None)
            g_a = float(np.sum((p - y) * zs) + ridge * a)
            g_b = float(np.sum(p - y))
            h_aa = float(np.sum(w * zs * zs) + ridge)
            h_ab = float(np.sum(w * zs))
            h_bb = float(np.sum(w))
            det = h_aa * h_bb - h_ab * h_ab
            if abs(det) < 1e-12:
                break
            d_a = (h_bb * g_a - h_ab * g_b) / det
            d_b = (h_aa * g_b - h_ab * g_a) / det
            d_a = float(np.clip(d_a, -max_step, max_step))
            d_b = float(np.clip(d_b, -max_step, max_step))
            a -= d_a
            b -= d_b
            self.iterations = step + 1
            if abs(d_a) < 1e-8 and abs(d_b) < 1e-8:
                break

        # 还原到原始 logit 尺度：a'·zs + b' = (a'/scale)·z + (b' - a'·mean/scale)
        a_raw = a / z_scale
        b_raw = b - a * z_mean / z_scale

        raw_brier = self._brier(y, sigmoid(z))
        calibrated = sigmoid(a * zs + b)
        calibrated_brier = self._brier(y, calibrated)
        if not np.isfinite(calibrated_brier) or calibrated_brier > raw_brier + 1e-9:
            self.a, self.b, self.fitted = 1.0, 0.0, False
            self.reason = (
                f"标定后 Brier({calibrated_brier:.4f}) 未优于原始输出({raw_brier:.4f})，"
                "自动回退到恒等映射"
            )
            return self

        self.a, self.b, self.fitted = float(a_raw), float(b_raw), True
        self.reason = (
            f"Brier 由 {raw_brier:.4f} 降至 {calibrated_brier:.4f}"
        )
        return self

    def transform(self, logit: float) -> float:
        if not self.fitted:
            return float(sigmoid(logit))
        return float(sigmoid(self.a * logit + self.b))

    def to_dict(self) -> dict[str, Any]:
        return {
            "a": self.a, "b": self.b, "fitted": self.fitted,
            "iterations": self.iterations, "reason": self.reason,
        }


# --------------------------------------------------------------------- 模型
class GatedABMIL:
    """门控注意力多示例学习（ABMIL）。"""

    def __init__(self, config: MilConfig | None = None) -> None:
        self.config = config or MilConfig()
        rng = np.random.default_rng(self.config.seed)
        d, m = self.config.in_dim, self.config.attn_dim
        # 门控注意力参数
        self.V = (rng.normal(0, 1.0 / math.sqrt(d), (m, d))).astype(np.float64)
        self.U = (rng.normal(0, 1.0 / math.sqrt(d), (m, d))).astype(np.float64)
        self.w = (rng.normal(0, 1.0 / math.sqrt(m), m)).astype(np.float64)
        # 分类头
        self.W = np.zeros(d, dtype=np.float64)
        self.b = 0.0
        # 特征标准化统计量（由训练集决定，推理时必须复用）
        self.feat_mean = np.zeros(d, dtype=np.float64)
        self.feat_std = np.ones(d, dtype=np.float64)
        self.scaler = PlattScaler()
        self.history: list[dict[str, float]] = []
        self.trained = False
        self.train_summary: dict[str, Any] = {}

        self._adam_state: dict[str, tuple[np.ndarray | float, np.ndarray | float]] = {}

    # ------------------------------------------------------------ 预处理
    def set_feature_stats(self, embeddings: Sequence[np.ndarray]) -> None:
        """用训练集全部图块统计标准化参数（生产环境应固化并随版本发布）。"""
        stacked = np.concatenate([np.asarray(e, dtype=np.float64).reshape(-1, self.config.in_dim)
                                  for e in embeddings if len(e)], axis=0)
        if stacked.size == 0:
            return
        self.feat_mean = stacked.mean(axis=0)
        self.feat_std = np.where(stacked.std(axis=0) < 1e-6, 1.0, stacked.std(axis=0))

    def _prepare(self, embeddings: np.ndarray) -> np.ndarray:
        arr = np.asarray(embeddings, dtype=np.float64).reshape(-1, self.config.in_dim)
        return (arr - self.feat_mean) / self.feat_std

    # --------------------------------------------------------------- 前向
    def forward(self, embeddings: np.ndarray) -> dict[str, np.ndarray | float]:
        h = self._prepare(embeddings)
        vh = h @ self.V.T
        uh = h @ self.U.T
        t = np.tanh(vh)
        s = sigmoid(uh)
        g = t * s
        a = g @ self.w
        attn = softmax(a)
        z = attn @ h
        logit = float(z @ self.W + self.b)
        prob = float(sigmoid(logit))
        return {"h": h, "vh": vh, "uh": uh, "t": t, "s": s, "g": g,
                "a": a, "attn": attn, "z": z, "logit": logit, "prob": prob}

    def predict(self, embeddings: np.ndarray) -> dict[str, Any]:
        """推理：返回概率、校准概率、注意力权重、top-k 区域序号。"""
        arr = np.asarray(embeddings, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[0] == 0:
            return {"probability": 0.0, "calibrated_probability": 0.0, "logit": 0.0,
                    "attention": [], "top_indices": [], "tile_count": 0}
        out = self.forward(arr)
        attn = np.asarray(out["attn"], dtype=np.float64)
        logit = float(out["logit"])
        return {
            "probability": float(out["prob"]),
            "calibrated_probability": self.scaler.transform(logit),
            "logit": logit,
            "attention": attn.tolist(),
            "top_indices": np.argsort(-attn).tolist(),
            "tile_count": int(arr.shape[0]),
            "attention_entropy": float(-np.sum(attn * np.log(np.clip(attn, 1e-12, None)))),
            "max_attention": float(attn.max()) if attn.size else 0.0,
        }

    # --------------------------------------------------------------- 反向
    def _backward(self, cache: dict[str, Any], label: float) -> dict[str, Any]:
        h, t, s, g = cache["h"], cache["t"], cache["s"], cache["g"]
        attn, z = cache["attn"], cache["z"]
        prob = float(cache["prob"])
        weight = self.config.pos_weight if label >= 0.5 else 1.0

        dlogit = weight * (prob - label)  # dL/dlogit（BCE + pos_weight）

        grads: dict[str, Any] = {}
        grads["W"] = z * dlogit + 2 * self.config.l2_reg * self.W
        grads["b"] = dlogit

        dz = dlogit * self.W
        dattn = h @ dz                              # (N,)
        da = attn * (dattn - float(dattn @ attn))   # softmax 雅可比
        dg = np.outer(da, self.w)                   # (N, M)
        grads["w"] = g.T @ da                       # (M,)

        dt = dg * s
        ds = dg * t
        dvh = dt * (1.0 - t * t)
        duh = ds * s * (1.0 - s)
        grads["V"] = dvh.T @ h
        grads["U"] = duh.T @ h
        return grads

    def _adam_step(self, grads: dict[str, Any], lr: float, t: int,
                   beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8) -> None:
        for key, grad in grads.items():
            m_key, v_key = f"m_{key}", f"v_{key}"
            m, v = self._adam_state.get(m_key), self._adam_state.get(v_key)
            if m is None:
                m = np.zeros_like(grad, dtype=np.float64)
                v = np.zeros_like(grad, dtype=np.float64)
            m = beta1 * m + (1 - beta1) * grad
            v = beta2 * v + (1 - beta2) * (grad * grad)
            self._adam_state[m_key], self._adam_state[v_key] = m, v
            m_hat = m / (1 - beta1 ** t)
            v_hat = v / (1 - beta2 ** t)
            update = lr * m_hat / (np.sqrt(v_hat) + eps)
            setattr(self, key, getattr(self, key) - update)

    # --------------------------------------------------------------- 训练
    @staticmethod
    def _auroc(labels: np.ndarray, scores: np.ndarray) -> float:
        pos = scores[labels >= 0.5]
        neg = scores[labels < 0.5]
        if pos.size == 0 or neg.size == 0:
            return 0.5
        order = np.argsort(scores)
        ranks = np.empty_like(order, dtype=np.float64)
        ranks[order] = np.arange(1, scores.size + 1)
        # 处理并列：用平均秩
        sorted_scores = scores[order]
        i = 0
        while i < sorted_scores.size:
            j = i
            while j + 1 < sorted_scores.size and sorted_scores[j + 1] == sorted_scores[i]:
                j += 1
            if j > i:
                ranks[order[i: j + 1]] = (i + j + 2) / 2.0
            i = j + 1
        pos_rank_sum = ranks[labels >= 0.5].sum()
        n_pos, n_neg = pos.size, neg.size
        return float((pos_rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))

    def fit(
        self,
        bags: Sequence[np.ndarray],
        labels: Sequence[float],
        val_bags: Sequence[np.ndarray] | None = None,
        val_labels: Sequence[float] | None = None,
        milestones: list[dict[str, Any]] | None = None,
        epochs: int | None = None,
        update_feature_stats: bool = True,
        lr_scale: float = 1.0,
        epoch_cb: Any = None,
        cancel_cb: Any = None,
    ) -> dict[str, Any]:
        """训练。返回训练摘要（含训练/验证 AUROC 曲线）。

        `update_feature_stats=False` 与 `epochs=` 供**联邦学习**的本地增量训练使用：
        本地只做若干轮梯度更新，标准化统计量沿用全局值（否则各节点统计口径不一致，
        FedAvg 平均出来的参数无法对应同一个特征空间）。
        """
        bags = [np.asarray(b, dtype=np.float32).reshape(-1, self.config.in_dim) for b in bags]
        y = np.asarray(labels, dtype=np.float64)
        keep = [i for i, b in enumerate(bags) if b.shape[0] > 0]
        bags = [bags[i] for i in keep]
        y = y[keep]
        if len(bags) == 0:
            raise ValueError("训练集为空：请先完成特征预计算")

        n_pos = float((y >= 0.5).sum())
        n_neg = float(len(y) - n_pos)
        if self.config.pos_weight <= 0:
            self.config.pos_weight = (n_neg / n_pos) if n_pos > 0 else 1.0

        if update_feature_stats:
            self.set_feature_stats(bags)
        self._adam_state = {}
        self.history = []
        total_epochs = int(epochs if epochs is not None else self.config.epochs)
        learning_rate = self.config.learning_rate * max(lr_scale, 1e-6)

        best_state: dict[str, Any] | None = None
        best_metric = -1.0
        patience = 0

        for epoch in range(1, total_epochs + 1):
            order = np.random.default_rng(self.config.seed + epoch).permutation(len(bags))
            epoch_loss = 0.0
            for idx in order:
                bag = bags[int(idx)]
                label = float(y[int(idx)])
                cache = self.forward(bag)
                epoch_loss += binary_cross_entropy(float(cache["prob"]), label, self.config.pos_weight)
                grads = self._backward(cache, label)
                self._adam_step(grads, learning_rate, epoch)

            mean_loss = epoch_loss / max(len(bags), 1)
            train_scores = np.array([float(self.forward(b)["prob"]) for b in bags])
            train_auroc = self._auroc(y, train_scores)
            record = {
                "epoch": epoch,
                "loss": round(mean_loss, 6),
                "train_auroc": round(train_auroc, 6),
            }
            if val_bags is not None and val_labels is not None and len(val_bags) > 0:
                v_bags = [np.asarray(b, dtype=np.float32).reshape(-1, self.config.in_dim) for b in val_bags]
                v_y = np.asarray(val_labels, dtype=np.float64)
                v_probs = np.array([float(self.forward(b)["prob"]) for b in v_bags])
                val_auroc = self._auroc(v_y, v_probs)
                v_loss = float(np.mean([
                    binary_cross_entropy(float(p), float(t), self.config.pos_weight)
                    for p, t in zip(v_probs, v_y)
                ]))
                record["val_auroc"] = round(val_auroc, 6)
                record["val_loss"] = round(v_loss, 6)
                # 复合监控指标：AUROC 主导，但用验证损失做平局决胜。
                # 只用 AUROC 会导致「排名一到位就早停」，此时 logit 幅度还很小、
                # 概率贴在中位附近 —— 排名指标漂亮，但置信度分级与拒识机制完全失效。
                monitor = val_auroc - 0.01 * v_loss
            else:
                monitor = train_auroc - 0.01 * mean_loss

            self.history.append(record)
            if milestones is not None and epoch in {1, total_epochs // 2, total_epochs}:
                milestones.append({"epoch": epoch, **record})
            # 逐轮上报进度与取消检查：训练是最容易被用户中途叫停的长任务
            if cancel_cb is not None:
                cancel_cb()
            if epoch_cb is not None:
                epoch_cb(epoch, total_epochs, monitor, record)

            # 以「当前模型 + 当前标定」在同一监控集上的表现择优
            if monitor > best_metric + 1e-5:
                best_metric = monitor
                patience = 0
                best_state = {
                    "V": self.V.copy(), "U": self.U.copy(), "w": self.w.copy(),
                    "W": self.W.copy(), "b": self.b,
                    "feat_mean": self.feat_mean.copy(), "feat_std": self.feat_std.copy(),
                    "epoch": epoch,
                }
            else:
                patience += 1
                if update_feature_stats and patience >= self.config.early_stop_patience:
                    logger.info("ABMIL 早停于第 %d 轮（监控指标 %.4f）", epoch, best_metric)
                    break

        if best_state:
            self.V = best_state["V"]
            self.U = best_state["U"]
            self.w = best_state["w"]
            self.W = best_state["W"]
            self.b = best_state["b"]
            self.feat_mean = best_state["feat_mean"]
            self.feat_std = best_state["feat_std"]
            self.train_summary["best_epoch"] = best_state["epoch"]

        # ---------- Platt 标定
        # 标定集优先用验证集；若验证集过小（<10 例，牛顿拟合不稳）则并入训练集一起拟合。
        # 小验证集下跳过标定会导致概率不锐化 —— 排名指标好看，但置信度分级与拒识形同虚设。
        if val_bags is not None and len(val_bags) >= 10:
            cal_bags, cal_labels, cal_source = list(val_bags), list(val_labels or []), "validation"
        else:
            cal_bags = list(val_bags or []) + list(bags)
            cal_labels = list(val_labels or []) + list(y)
            cal_source = "validation+train（验证集不足 10 例）"
        logits = [float(self.forward(np.asarray(b, dtype=np.float32).reshape(-1, self.config.in_dim))["logit"])
                  for b in cal_bags]
        self.scaler = PlattScaler().fit(logits, cal_labels)

        train_scores = np.array([float(self.forward(b)["prob"]) for b in bags])
        self.trained = True
        self.train_summary.update({
            "bag_count": len(bags),
            "positive_count": int(n_pos),
            "negative_count": int(n_neg),
            "pos_weight": round(float(self.config.pos_weight), 4),
            "final_train_auroc": round(self._auroc(y, train_scores), 6),
            "best_monitor": round(best_metric, 6),
            "epochs_run": len(self.history),
            "platt": self.scaler.to_dict(),
            "calibration_source": cal_source,
            "trained_at": datetime.now().isoformat(timespec="seconds"),
        })
        return self.train_summary

    # ------------------------------------------------------------- 落盘
    def state_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "V": self.V.tolist(),
            "U": self.U.tolist(),
            "w": self.w.tolist(),
            "W": self.W.tolist(),
            "b": self.b,
            "feat_mean": self.feat_mean.tolist(),
            "feat_std": self.feat_std.tolist(),
            "scaler": self.scaler.to_dict(),
            "train_summary": self.train_summary,
        }

    @classmethod
    def from_state_dict(cls, payload: dict[str, Any]) -> "GatedABMIL":
        cfg = MilConfig(**{k: v for k, v in (payload.get("config") or {}).items()
                           if k in MilConfig.__dataclass_fields__})
        model = cls(cfg)
        model.V = np.asarray(payload["V"], dtype=np.float64)
        model.U = np.asarray(payload["U"], dtype=np.float64)
        model.w = np.asarray(payload["w"], dtype=np.float64)
        model.W = np.asarray(payload["W"], dtype=np.float64)
        model.b = float(payload["b"])
        model.feat_mean = np.asarray(payload.get("feat_mean", np.zeros(cfg.in_dim)), dtype=np.float64)
        model.feat_std = np.asarray(payload.get("feat_std", np.ones(cfg.in_dim)), dtype=np.float64)
        scaler_payload = payload.get("scaler") or {}
        scaler = PlattScaler()
        scaler.a = float(scaler_payload.get("a", 1.0))
        scaler.b = float(scaler_payload.get("b", 0.0))
        scaler.fitted = bool(scaler_payload.get("fitted", False))
        model.scaler = scaler
        model.train_summary = payload.get("train_summary") or {}
        model.trained = True
        return model

    def save(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.state_dict()
        if target.suffix == ".json":
            target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        else:
            np.savez_compressed(
                target.with_suffix(".npz"),
                config=json.dumps(payload["config"]),
                V=np.asarray(payload["V"], dtype=np.float32),
                U=np.asarray(payload["U"], dtype=np.float32),
                w=np.asarray(payload["w"], dtype=np.float32),
                W=np.asarray(payload["W"], dtype=np.float32),
                b=np.asarray([payload["b"]], dtype=np.float32),
                feat_mean=np.asarray(payload["feat_mean"], dtype=np.float32),
                feat_std=np.asarray(payload["feat_std"], dtype=np.float32),
                scaler=json.dumps(payload["scaler"]),
                train_summary=json.dumps(payload["train_summary"], ensure_ascii=False),
            )
            return str(target.with_suffix(".npz"))
        return str(target)

    @classmethod
    def load(cls, path: str | Path) -> "GatedABMIL":
        target = Path(path)
        if target.suffix == ".json":
            return cls.from_state_dict(json.loads(target.read_text(encoding="utf-8")))
        data = np.load(target if target.suffix == ".npz" else target.with_suffix(".npz"), allow_pickle=False)
        payload = {
            "config": json.loads(str(data["config"])),
            "V": data["V"].tolist(),
            "U": data["U"].tolist(),
            "w": data["w"].tolist(),
            "W": data["W"].tolist(),
            "b": float(data["b"][0]),
            "feat_mean": data["feat_mean"].tolist(),
            "feat_std": data["feat_std"].tolist(),
            "scaler": json.loads(str(data["scaler"])),
            "train_summary": json.loads(str(data["train_summary"])),
        }
        return cls.from_state_dict(payload)


# ------------------------------------------------------------------ 置信度分级
def confidence_level(calibrated_probability: float, attention_entropy: float,
                     tile_count: int, evidence_count: int = 3) -> str:
    """置信度三级（high / medium / low）。

    判据同时考虑概率的确定性、注意力分布的集中度（熵越低越聚焦）与证据充分性。
    这直接决定是否触发拒识（低置信度转人工）。

    权重刻意保持克制：注意力熵惩罚只占 0.18 —— 病理阅片中诊断依据本就可能分散在
    多个区域，把「注意力分散」等同于「不可信」会造成大量无谓拒识，反而损害可用性。
    """
    p = calibrated_probability
    certainty = max(p, 1 - p)
    if tile_count < 8 or evidence_count < 1:
        return "low"
    entropy_penalty = 0.0
    if tile_count > 1:
        entropy_penalty = attention_entropy / math.log(tile_count)
    score = certainty - 0.18 * entropy_penalty
    if score >= 0.88:
        return "high"
    if score >= 0.70:
        return "medium"
    return "low"


def encode_summary_for_storage(prediction: dict[str, Any], top_k: int = 8) -> str:
    """把预测结果压缩成可入库的摘要 JSON。"""
    top = prediction.get("top_indices") or []
    attn = prediction.get("attention") or []
    return json.dumps(
        {
            "tile_count": prediction.get("tile_count", 0),
            "max_attention": round(float(prediction.get("max_attention", 0.0)), 6),
            "attention_entropy": round(float(prediction.get("attention_entropy", 0.0)), 6),
            "top_indices": [int(i) for i in top[:top_k]],
            "top_attention": [round(float(attn[i]), 6) for i in top[:top_k] if i < len(attn)],
        },
        ensure_ascii=False,
    )
