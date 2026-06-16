"""Train and export the Bengaluru area-risk model.

Generates the synthetic priors-conditioned dataset, trains the classifier,
prints metrics, and saves the joblib bundle.

Run:  uv run python -m scripts.train_risk_model
      uv run python -m scripts.train_risk_model --days 90 --samples 60000
"""

from __future__ import annotations

import argparse

from app.core.logging import get_logger
from app.ml.dataset import build_dataset
from app.ml.risk_model import predict_risk, save_bundle, train_model

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the area-risk model.")
    parser.add_argument("--days", type=int, default=90, help="days to simulate")
    parser.add_argument("--samples", type=int, default=60_000, help="training rows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None, help="output joblib path")
    args = parser.parse_args()

    log.info("Building dataset (days=%d, samples=%d)...", args.days, args.samples)
    data = build_dataset(n_days=args.days, n_samples=args.samples, seed=args.seed)
    log.info("Positive rate: %.3f", data.meta["positive_rate"])

    result = train_model(data, seed=args.seed)
    path = save_bundle(result.bundle, args.out)

    print("\n=== Area-risk model trained ===")
    for k, v in result.metrics.items():
        print(f"  {k:14s}: {v}")
    print(f"  artifact      : {path}")

    # Quick sanity demo: same spot, day vs night.
    from datetime import UTC, datetime

    lat, lon = 12.9770, 77.5720  # Majestic (high-risk zone)
    day = predict_risk(lat, lon, datetime(2026, 6, 16, 10, tzinfo=UTC),
                       bundle=result.bundle)
    night = predict_risk(lat, lon, datetime(2026, 6, 20, 22, tzinfo=UTC),
                         bundle=result.bundle)
    park_day = predict_risk(12.9760, 77.5950, datetime(2026, 6, 16, 10, tzinfo=UTC),
                           bundle=result.bundle)
    print("\n=== Sanity check (risk probability) ===")
    print(f"  Majestic, Tue 10:00 : {day:.3f}")
    print(f"  Majestic, Sat 22:00 : {night:.3f}")
    print(f"  Cubbon Park, Tue 10:00: {park_day:.3f}")


if __name__ == "__main__":
    main()
