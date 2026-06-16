"""Pluggable text embeddings for risk-event vectors (pgvector, 384-d).

The default is a lightweight **deterministic hashing embedder**: no heavy
dependencies, runs fully offline, and gives stable vectors for storage and
nearest-neighbour plumbing. It does NOT capture deep semantic similarity — swap
in a real sentence-transformer later (same 384-d) without touching callers.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.db.models import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _token_hash(token: str) -> int:
    return int.from_bytes(hashlib.md5(token.encode()).digest()[:4], "little")


def hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic bag-of-words hashing embedding, L2-normalized."""
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall(text.lower())
    for tok in tokens:
        h = _token_hash(tok)
        idx = h % dim
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def embed(text: str) -> list[float]:
    """Embed text into a 384-d vector (default hashing embedder)."""
    return hash_embedding(text)
