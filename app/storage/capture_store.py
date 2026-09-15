from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.time_utils import iso_now


class CaptureStore:
    """JSON store for target contacts and processed recording docs."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write(self._empty())

    @staticmethod
    def _empty() -> Dict[str, Any]:
        return {
            "targets": {},
            "processed_files": {},
            "runs": [],
        }

    def _read(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return self._empty()
        with self.file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("targets", {})
        data.setdefault("processed_files", {})
        data.setdefault("runs", [])
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_targets(self) -> List[Dict[str, Any]]:
        targets = self._read().get("targets", {})
        return sorted(targets.values(), key=lambda item: (str(item.get("name") or ""), str(item.get("target_key") or "")))

    def upsert_target(self, user: Dict[str, Any]) -> Dict[str, Any]:
        target_key = self._target_key(user)
        if not target_key:
            raise ValueError("target user must include open_id or user_id")

        record = {
            "target_key": target_key,
            "name": user.get("name") or user.get("en_name") or "",
            "en_name": user.get("en_name") or "",
            "open_id": user.get("open_id") or "",
            "user_id": user.get("user_id") or "",
            "union_id": user.get("union_id") or "",
            "email": user.get("email") or "",
            "mobile": user.get("mobile") or "",
            "added_at": iso_now(),
        }
        data = self._read()
        existing = data["targets"].get(target_key, {})
        if existing.get("added_at"):
            record["added_at"] = existing["added_at"]
        record["updated_at"] = iso_now()
        data["targets"][target_key] = record
        self._write(data)
        return record

    def delete_target(self, target_key: str) -> bool:
        data = self._read()
        existed = target_key in data["targets"]
        data["targets"].pop(target_key, None)
        self._write(data)
        return existed

    def get_processed(self, file_key: str) -> Optional[Dict[str, Any]]:
        return self._read().get("processed_files", {}).get(file_key)

    def mark_processed(self, file_key: str, record: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        saved = {
            **record,
            "file_key": file_key,
            "processed_at": iso_now(),
        }
        data["processed_files"][file_key] = saved
        self._write(data)
        return saved

    def append_run(self, record: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        saved = {
            **record,
            "run_at": iso_now(),
        }
        runs = data.setdefault("runs", [])
        runs.append(saved)
        data["runs"] = runs[-50:]
        self._write(data)
        return saved

    def list_runs(self) -> List[Dict[str, Any]]:
        return list(reversed(self._read().get("runs", [])))

    @staticmethod
    def _target_key(user: Dict[str, Any]) -> str:
        return str(user.get("open_id") or user.get("user_id") or "").strip()
