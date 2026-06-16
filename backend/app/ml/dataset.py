"""Synthetic spatiotemporal incident dataset for the Bengaluru risk model.

Pipeline (priors-conditioned, fully offline & reproducible):
  1. Simulate an hourly incident **event log** over the Bengaluru grid. The
     expected count per (cell, hour) is a Poisson rate driven by the cell's
     spatial prior (`bengaluru_priors.spatial_intensity`) and the hour/day
     temporal multiplier.
  2. Derive supervised **training rows**: for sampled (cell, hour) points the
     label is "did an incident occur this hour", and `recent_incidents` is the
     count in that cell over the trailing window. Features come from
     `app.ml.features` so training and serving stay in lockstep.

This yields a genuine spatiotemporal learning task: the model must recover risk
from coordinates + time + recent counts, not from the hidden intensity itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from app.ml.bengaluru_priors import (
    cell_center,
    grid_shape,
    spatial_intensity,
    temporal_multiplier,
)
from app.ml.features import FEATURE_NAMES, build_features

# Scales the Poisson rate so positives are realistically sparse but learnable.
DEFAULT_BASE_SCALE = 0.10
DEFAULT_WINDOW_HOURS = 24
# Label horizon: an area is "risky now" if an incident occurs in the cell within
# the next few hours. Aggregating forward reduces per-hour Poisson noise and
# matches the product question "how risky is this area in the near term".
DEFAULT_HORIZON_HOURS = 6


@dataclass
class DatasetBundle:
    frame: pd.DataFrame  # FEATURE_NAMES + "label"
    cell_baseline: np.ndarray  # mean recent_incidents per flattened cell
    meta: dict


def _cell_spatial_grid() -> np.ndarray:
    """Spatial intensity per cell, flattened (row-major)."""
    n_rows, n_cols = grid_shape()
    out = np.zeros(n_rows * n_cols, dtype=float)
    for r in range(n_rows):
        for c in range(n_cols):
            lat, lon = cell_center(r, c)
            out[r * n_cols + c] = spatial_intensity(lat, lon)
    return out


def simulate_incident_counts(
    n_days: int = 60,
    base_scale: float = DEFAULT_BASE_SCALE,
    *,
    start: datetime | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, datetime]:
    """Hourly incident counts, shape (n_hours, n_cells). Row-major cell order."""
    rng = np.random.default_rng(seed)
    n_hours = n_days * 24
    start = start or datetime(2026, 1, 1, tzinfo=UTC)

    spatial = _cell_spatial_grid()  # (n_cells,)

    # Temporal multiplier per hour index.
    temporal = np.array(
        [
            temporal_multiplier((start + timedelta(hours=h)).hour,
                                (start + timedelta(hours=h)).weekday())
            for h in range(n_hours)
        ]
    )  # (n_hours,)

    # Outer product -> rate matrix, then Poisson draw.
    rates = base_scale * np.outer(temporal, spatial)  # (n_hours, n_cells)
    counts = rng.poisson(rates).astype(np.int32)
    return counts, start


def build_dataset(
    n_days: int = 60,
    n_samples: int = 40_000,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    base_scale: float = DEFAULT_BASE_SCALE,
    *,
    seed: int = 42,
) -> DatasetBundle:
    """Build the supervised training frame + per-cell recent-count baseline.

    Label = 1 if an incident occurs in the cell within the next `horizon_hours`.
    `recent_incidents` feature = incidents in the cell over the trailing
    `window_hours`.
    """
    counts, start = simulate_incident_counts(
        n_days=n_days, base_scale=base_scale, seed=seed
    )
    n_hours, n_cells = counts.shape
    n_rows, n_cols = grid_shape()
    rng = np.random.default_rng(seed + 1)

    # Cumulative sum so windowed counts are O(1) to look up.
    cumulative = np.cumsum(counts, axis=0)  # (n_hours, n_cells)

    def _range_sum(lo: int, hi: int, cell: int) -> int:
        """Sum of counts[lo:hi, cell] (hi exclusive), clamped to bounds."""
        lo = max(0, lo)
        hi = min(n_hours, hi)
        if hi <= lo:
            return 0
        upper = cumulative[hi - 1, cell]
        lower = cumulative[lo - 1, cell] if lo > 0 else 0
        return int(upper - lower)

    def recent_count(h: int, cell: int) -> int:
        return _range_sum(h - window_hours, h, cell)

    def forward_label(h: int, cell: int) -> int:
        return 1 if _range_sum(h, h + horizon_hours, cell) > 0 else 0

    # Per-cell baseline = mean trailing-window count across valid hours (for
    # inference fallback when a live recent count isn't supplied).
    valid_lo, valid_hi = window_hours, n_hours - horizon_hours
    trailing = cumulative[valid_lo:valid_hi] - cumulative[
        valid_lo - window_hours : valid_hi - window_hours
    ]
    cell_baseline = trailing.mean(axis=0)  # (n_cells,)

    # Sample (hour, cell) points from valid hours (need trailing + forward room).
    sample_hours = rng.integers(valid_lo, valid_hi, size=n_samples)
    sample_cells = rng.integers(0, n_cells, size=n_samples)

    rows: list[list[float]] = []
    labels: list[int] = []
    for h, cell in zip(sample_hours.tolist(), sample_cells.tolist(), strict=True):
        r, c = divmod(cell, n_cols)
        lat, lon = cell_center(r, c)
        when = start + timedelta(hours=h)
        feats = build_features(lat, lon, when, recent_incidents=recent_count(h, cell))
        rows.append([feats[name] for name in FEATURE_NAMES])
        labels.append(forward_label(h, cell))

    frame = pd.DataFrame(rows, columns=FEATURE_NAMES)
    frame["label"] = labels

    meta = {
        "n_days": n_days,
        "n_samples": n_samples,
        "window_hours": window_hours,
        "horizon_hours": horizon_hours,
        "base_scale": base_scale,
        "grid_shape": [n_rows, n_cols],
        "positive_rate": float(np.mean(labels)),
        "seed": seed,
    }
    return DatasetBundle(frame=frame, cell_baseline=cell_baseline, meta=meta)
