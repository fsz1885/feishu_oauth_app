from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def expires_at_from_seconds(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    return (now_utc() + timedelta(seconds=int(seconds))).isoformat()


def is_expired(iso_str: Optional[str], *, skew_seconds: int = 120) -> bool:
    if not iso_str:
        return True
    try:
        expires_at = datetime.fromisoformat(iso_str)
    except ValueError:
        return True
    return now_utc() >= (expires_at - timedelta(seconds=skew_seconds))
