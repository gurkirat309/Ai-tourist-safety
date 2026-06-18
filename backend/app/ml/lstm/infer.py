"""Inference for the LSTM trajectory-anomaly model — **graceful**.

`score_trajectory` returns an anomaly probability in [0, 1], or **None** if
torch isn't installed or the model artifact is missing. This keeps the advisory
signal entirely optional: the deterministic detectors remain the safety floor.
"""

from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.lstm.features import make_window

log = get_logger(__name__)


@lru_cache(maxsize=1)
def _load(path: str | None = None):
    """Load (model, meta) or (None, None) if torch/model unavailable."""
    path = path or get_settings().lstm_model_path
    try:
        import torch

        from app.ml.lstm.model import TrajectoryLSTM
    except Exception as exc:  # noqa: BLE001
        log.info("LSTM unavailable (torch not installed): %s", exc)
        return None, None
    if not os.path.exists(path):
        log.info("LSTM model not found at %s (advisory signal disabled)", path)
        return None, None

    bundle = torch.load(path, map_location="cpu", weights_only=False)
    model = TrajectoryLSTM()
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    return model, bundle.get("meta", {})


def lstm_available() -> bool:
    model, _ = _load()
    return model is not None


def score_trajectory(points: list[tuple[float, float, float]]) -> float | None:
    """Anomaly probability for a trajectory (list of (lat, lon, t_seconds))."""
    model, _ = _load()
    if model is None or len(points) < 2:
        return None
    import torch

    window = make_window(points)  # (W, F)
    x = torch.from_numpy(window).unsqueeze(0)  # (1, W, F)
    with torch.no_grad():
        prob = torch.sigmoid(model(x)).item()
    return float(prob)
