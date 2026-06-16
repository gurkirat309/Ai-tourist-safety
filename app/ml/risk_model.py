"""Area-risk model: train, persist, and serve `(location, time) -> risk score`.

The only trained model in the system. It is a classical tabular gradient-boosted
classifier (scikit-learn `HistGradientBoostingClassifier`) — no GPU, no deep
learning. The persisted artifact is a self-contained bundle (model + per-cell
recent-count baseline + feature order + metadata) so inference needs nothing
but the joblib file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.bengaluru_priors import cell_index, grid_shape
from app.ml.dataset import DatasetBundle, build_dataset
from app.ml.features import FEATURE_NAMES, build_features, features_to_row

log = get_logger(__name__)


@dataclass
class TrainResult:
    bundle: dict[str, Any]
    metrics: dict[str, float]


def train_model(
    data: DatasetBundle | None = None,
    *,
    test_size: float = 0.25,
    seed: int = 42,
) -> TrainResult:
    """Train the classifier and return a serializable bundle + metrics."""
    if data is None:
        log.info("No dataset supplied; generating synthetic dataset...")
        data = build_dataset(seed=seed)

    frame = data.frame
    X = frame[FEATURE_NAMES].to_numpy(dtype=float)
    y = frame["label"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )

    clf = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.08,
        max_depth=6,
        l2_regularization=1.0,
        random_state=seed,
    )
    clf.fit(X_train, y_train)

    proba = clf.predict_proba(X_test)[:, 1]
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "avg_precision": float(average_precision_score(y_test, proba)),
        "positive_rate": float(np.mean(y)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }
    log.info(
        "Trained area-risk model: ROC-AUC=%.3f AP=%.3f (pos_rate=%.3f)",
        metrics["roc_auc"], metrics["avg_precision"], metrics["positive_rate"],
    )

    bundle = {
        "model": clf,
        "feature_names": FEATURE_NAMES,
        "cell_baseline": data.cell_baseline,
        "grid_shape": list(grid_shape()),
        "meta": {**data.meta, "metrics": metrics},
    }
    return TrainResult(bundle=bundle, metrics=metrics)


def save_bundle(bundle: dict[str, Any], path: str | None = None) -> str:
    path = path or get_settings().risk_model_path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(bundle, path)
    log.info("Saved area-risk model bundle -> %s", path)
    return path


@lru_cache(maxsize=1)
def load_bundle(path: str | None = None) -> dict[str, Any]:
    path = path or get_settings().risk_model_path
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Risk model not found at '{path}'. Train it first: "
            "`uv run python -m scripts.train_risk_model`."
        )
    return joblib.load(path)


def _baseline_recent(bundle: dict[str, Any], lat: float, lon: float) -> float:
    n_cols = bundle["grid_shape"][1]
    r, c = cell_index(lat, lon)
    flat = r * n_cols + c
    baseline = bundle["cell_baseline"]
    if 0 <= flat < len(baseline):
        return float(baseline[flat])
    return 0.0


def predict_risk(
    lat: float,
    lon: float,
    when: datetime,
    recent_incidents: float | None = None,
    *,
    bundle: dict[str, Any] | None = None,
) -> float:
    """Return the area-risk probability in [0, 1] for a (location, time).

    If `recent_incidents` is not supplied, the per-cell training baseline is
    used so the function is self-contained at serve time.
    """
    bundle = bundle or load_bundle()
    if recent_incidents is None:
        recent_incidents = _baseline_recent(bundle, lat, lon)

    feats = build_features(lat, lon, when, recent_incidents=recent_incidents)
    row = np.array([features_to_row(feats)], dtype=float)
    return float(bundle["model"].predict_proba(row)[0, 1])
