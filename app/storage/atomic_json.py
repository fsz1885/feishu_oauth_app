from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class AtomicJsonStore:
    """Base class for JSON-file stores: locked, atomic, corruption-tolerant.

    - All reads/writes are serialized with an RLock so background scheduler
      threads and HTTP request threads cannot clobber each other.
    - Writes go to a temp file first and are moved into place with os.replace,
      so a crash mid-write can never leave a half-written store behind.
    - An unreadable/corrupt store file is renamed to *.corrupt.<timestamp>
      (preserving the evidence) and a fresh empty store is created instead of
      crash-looping the whole service.
    """

    def __init__(self, file_path: str, empty_factory: Callable[[], Dict[str, Any]]):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._empty_factory = empty_factory
        if not self.file_path.exists():
            self._write(self._empty_factory())

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            if not self.file_path.exists():
                return self._empty_factory()
            try:
                with self.file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("store root is not a JSON object")
                return data
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                backup = self.file_path.with_name(
                    self.file_path.name + f".corrupt.{time.strftime('%Y%m%d_%H%M%S')}"
                )
                try:
                    self.file_path.rename(backup)
                except OSError:
                    backup = None
                logger.error(
                    "store file %s unreadable (%s); backed up to %s, recreating empty store",
                    self.file_path,
                    exc,
                    backup or "(backup failed)",
                )
                data = self._empty_factory()
                self._write(data)
                return data

    def _write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            tmp = self.file_path.with_name(self.file_path.name + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.file_path)
