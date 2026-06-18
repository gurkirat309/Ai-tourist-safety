"""Train and export the LSTM trajectory-anomaly model.

Builds the labeled window dataset, trains a small LSTM classifier, prints
metrics, and saves the artifact to models/trajectory_lstm.pt.

Run:  uv run python -m scripts.train_lstm   (needs the [lstm] extra / torch)
"""

from __future__ import annotations

import argparse
import os

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.lstm.dataset import build_dataset

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the trajectory-anomaly LSTM.")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--combos", type=int, default=150, help="trajectory pairs to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    import torch
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from torch import nn

    from app.ml.lstm.model import TrajectoryLSTM

    log.info("Building dataset (combos=%d)...", args.combos)
    X, y = build_dataset(n_per_combo=args.combos, seed=args.seed)
    log.info("dataset: %d windows, positive rate %.3f", len(y), float(np.mean(y)))

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=args.seed, stratify=y
    )
    torch.manual_seed(args.seed)
    model = TrajectoryLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(X_tr)
    yt = torch.from_numpy(y_tr.astype("float32"))
    n = len(Xt)

    model.train()
    for epoch in range(args.epochs):
        perm = torch.randperm(n)
        total = 0.0
        for i in range(0, n, args.batch):
            idx = perm[i : i + args.batch]
            opt.zero_grad()
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        if (epoch + 1) % 5 == 0:
            log.info("epoch %2d/%d avg_loss=%.4f", epoch + 1, args.epochs, total / n)

    model.eval()
    with torch.no_grad():
        proba = torch.sigmoid(model(torch.from_numpy(X_te))).numpy()
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_te, pred)),
        "roc_auc": float(roc_auc_score(y_te, proba)),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "positive_rate": float(np.mean(y)),
    }

    path = args.out or get_settings().lstm_model_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "meta": metrics}, path)

    print("\n=== Trajectory LSTM trained ===")
    for k, v in metrics.items():
        print(f"  {k:13s}: {v}")
    print(f"  artifact     : {path}")

    # Sanity: score a clean vs a deviating trajectory.
    from datetime import UTC, datetime

    from app.ml.lstm.infer import _load, score_trajectory
    from scripts.synthetic import Scenario, generate_trajectory

    _load.cache_clear()
    route = [(77.609, 12.975), (77.603, 12.9755), (77.598, 12.9758), (77.595, 12.976)]
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)

    def pts(pings):
        return [(p.lat, p.lon, p.recorded_at.timestamp()) for p in pings]

    normal = pts(generate_trajectory(route, scenario=Scenario.NORMAL, n_points=30,
                                     start_time=start, interval_s=60, seed=7))
    dev = pts(generate_trajectory(route, scenario=Scenario.DEVIATING, n_points=30,
                                  start_time=start, interval_s=60, seed=7))
    print("\n=== Sanity (anomaly probability) ===")
    print(f"  normal trajectory   : {score_trajectory(normal):.3f}")
    print(f"  deviating trajectory: {score_trajectory(dev):.3f}")


if __name__ == "__main__":
    main()
