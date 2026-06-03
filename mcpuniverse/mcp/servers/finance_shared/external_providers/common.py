"""Shared utilities for external finance provider adapters."""
import hashlib
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_HTTP_RETRY_ATTEMPTS = 3
DEFAULT_HTTP_RETRY_DELAY_SECONDS = 1


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize payloads deterministically for content hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    """Return the SHA-256 digest for a JSON-serializable payload."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """Fetch JSON from an external provider using the standard library."""
    last_error: Exception | None = None
    for attempt_number in range(1, DEFAULT_HTTP_RETRY_ATTEMPTS + 1):
        request = Request(url, headers=headers or {})
        try:
            with urlopen(request, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Provider returned HTTP {exc.code} for {redact_url(url)}") from exc
        except (TimeoutError, URLError) as exc:
            last_error = exc
            if attempt_number == DEFAULT_HTTP_RETRY_ATTEMPTS:
                break
            time.sleep(DEFAULT_HTTP_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"Failed to fetch provider JSON after {DEFAULT_HTTP_RETRY_ATTEMPTS} attempts: {redact_url(url)}"
    ) from last_error


def redact_url(url: str) -> str:
    """Redact secret query parameters from provider URLs before error reporting."""
    parsed_url = urlsplit(url)
    redacted_query = urlencode([
        (key, "***" if key.lower() in {"apikey", "api_key"} else value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
    ])
    return urlunsplit((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        redacted_query,
        parsed_url.fragment,
    ))
