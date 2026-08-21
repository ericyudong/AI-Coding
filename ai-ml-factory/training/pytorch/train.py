"""PyTorch ResNet-style smoke trainer that exports TorchScript for Triton."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class TinyNet(nn.Module):
    def __init__(self, n_classes: int = 10):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(3 * 32 * 32, 256),
            nn.ReLU(),
            nn.Linear(256, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="artifacts/vision-resnet/v0.0.0-local")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    device = torch.device(args.device)
    x = torch.randn(512, 3, 32, 32)
    y = torch.randint(0, 10, (512,))
    loader = DataLoader(TensorDataset(x, y), batch_size=64, shuffle=True)
    model = TinyNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    last_loss = 0.0
    for _ in range(args.epochs):
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            last_loss = float(loss.item())

    model.eval()
    example = torch.randn(1, 3, 32, 32, device=device)
    scripted = torch.jit.trace(model, example)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scripted.save(str(out / "model.pt"))
    metrics = {"loss": last_loss, "framework": "pytorch", "export": "torchscript", "device": args.device}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({"out_dir": str(out), **metrics}, indent=2))


if __name__ == "__main__":
    main()
