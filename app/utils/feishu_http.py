from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

RATE_LIMITED_HTTP_STATUS = 429
RATE_LIMITED_ERROR_CODE = 99991400


def is_rate_limited(status_code: int, result: Any) -> bool:
    """Detect Feishu rate limiting: HTTP 429 or business code 99991400."""
    if status_code == RATE_LIMITED_HTTP_STATUS:
        return True
    return isinstance(result, dict) and result.get("code") == RATE_LIMITED_ERROR_CODE


def request_json_with_backoff(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    max_retries: int = 2,
    base_delay: float = 2.0,
) -> requests.Response:
    """Send a request, retrying with exponential backoff when rate limited.

    Only HTTP 429 / code 99991400 are retried; other failures are returned
    immediately so each service keeps its existing error semantics.
    """
    resp = None
    for attempt in range(max_retries + 1):
        resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)
        if attempt >= max_retries:
            return resp
        try:
            result = resp.json()
        except ValueError:
            return resp
        if not is_rate_limited(resp.status_code, result):
            return resp
        delay = base_delay * (2 ** attempt)
        logger.warning(
            "Feishu rate limited on %s %s (HTTP %s), backoff %.1fs then retry (%d/%d)",
            method.upper(),
            url,
            resp.status_code,
            delay,
            attempt + 1,
            max_retries,
        )
        time.sleep(delay)
    return resp
