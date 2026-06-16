"""Make outbound HTTPS trust the OS certificate store.

Behind a TLS-intercepting proxy (corporate / antivirus), the custom root CA is
in the OS trust store but not in certifi (which httpx/openai use by default).
`truststore.inject_into_ssl()` routes Python SSL through the OS store so the
LLM and RSS HTTPS calls succeed. Idempotent; safe to call repeatedly.
"""

from __future__ import annotations

from app.core.logging import get_logger

log = get_logger(__name__)

_INJECTED = False


def ensure_system_tls() -> None:
    global _INJECTED
    if _INJECTED:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
        _INJECTED = True
        log.info("truststore injected: HTTPS will use the OS certificate store")
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not inject truststore (%s); using default certs", exc)
