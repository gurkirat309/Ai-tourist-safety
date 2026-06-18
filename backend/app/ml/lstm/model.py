"""LSTM trajectory-anomaly classifier (PyTorch).

A small LSTM over a window of movement features → P(anomalous). Importing this
module requires torch (optional `[lstm]` extra); callers that must stay
torch-free should not import it directly.
"""

from __future__ import annotations

import torch
from torch import nn

from app.ml.lstm.features import FEATURE_DIM


class TrajectoryLSTM(nn.Module):
    def __init__(self, input_dim: int = FEATURE_DIM, hidden: int = 32, layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, num_layers=layers, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, window, features)
        _, (h_n, _) = self.lstm(x)
        logit = self.head(h_n[-1]).squeeze(-1)  # (batch,)
        return logit
