"""Provider-agnostic LLM wrapper.

Groq is the default provider; it exposes an OpenAI-compatible API, so we use the
OpenAI SDK pointed at Groq's `base_url`. Provider, base_url, model, and key all
come from env — switching providers is an env change, not a code change.

A **dry-run mode** returns a canned structured response so all agent code is
fully testable without network access or an API key. Tests pass `dry_run=True`
explicitly rather than relying on env.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LLMClient:
    """Thin wrapper exposing a single JSON-extraction method."""

    def __init__(
        self,
        *,
        dry_run: bool | None = None,
        dry_run_response: dict[str, Any] | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self._base_url = settings.llm_base_url
        self._api_key = settings.llm_api_key
        # Dry-run when explicitly requested, or when no key / env flag set.
        self.dry_run = dry_run if dry_run is not None else not settings.llm_enabled
        self._dry_run_response = dry_run_response
        self._client = None  # lazily created real client

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI

            from app.services.tls import ensure_system_tls

            ensure_system_tls()  # trust the OS cert store (proxy-friendly)
            self._client = OpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

    def extract_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Call the model and parse a JSON object from the response.

        In dry-run mode returns the canned response (or an empty events list).
        """
        if self.dry_run:
            log.info("LLM dry-run: returning canned response (provider=%s)", self.provider)
            return self._dry_run_response or {"events": []}

        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            log.warning("LLM returned non-JSON content; coercing to empty result")
            return {"events": []}
