from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.storage.atomic_json import AtomicJsonStore
from app.utils.time_utils import iso_now


class CaptureStore(AtomicJsonStore):
    """JSON store for target contacts and processed recording docs.

    Read-modify-write cycles are serialized by the inherited RLock; writes are
    atomic and a corrupted file is backed up and rebuilt instead of crashing.
    """

    def __init__(self, file_path: str):
        super().__init__(file_path, self._empty)
        self._processed_keys: Optional[set] = None

    @staticmethod
    def _empty() -> Dict[str, Any]:
        return {
            "targets": {},
            "processed_files": {},
            "runs": [],
            "settings": {},
            "settings_history": [],
        }

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
        with self._lock:
            data = self._read()
            existing = data["targets"].get(target_key, {})
            if existing.get("added_at"):
                record["added_at"] = existing["added_at"]
            record["updated_at"] = iso_now()
            data["targets"][target_key] = record
            self._write(data)
        return record

    def delete_target(self, target_key: str) -> bool:
        with self._lock:
            data = self._read()
            existed = target_key in data["targets"]
            data["targets"].pop(target_key, None)
            self._write(data)
            return existed

    def get_processed(self, file_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._processed_keys is None:
                self._processed_keys = set(self._read().get("processed_files", {}).keys())
            if file_key not in self._processed_keys:
                return None
            return self._read().get("processed_files", {}).get(file_key)

    def mark_processed(self, file_key: str, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            saved = {
                **record,
                "file_key": file_key,
                "processed_at": iso_now(),
            }
            data["processed_files"][file_key] = saved
            if self._processed_keys is None:
                self._processed_keys = set(data["processed_files"].keys())
            else:
                self._processed_keys.add(file_key)
            self._write(data)
            return saved

    def append_run(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
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

    def get_setting(self, key: str) -> Optional[str]:
        value = self._read().get("settings", {}).get(key)
        return str(value) if value else None

    def set_setting(self, key: str, value: str, *, changed_by: str = "frontend") -> Dict[str, Any]:
        with self._lock:
            data = self._read()
            previous = data.get("settings", {}).get(key)
            data.setdefault("settings", {})[key] = value
            history = data.setdefault("settings_history", [])
            history.append({
                "key": key,
                "changed_by": changed_by,
                "changed_at": iso_now(),
                "previous": self.mask_token(str(previous)) if previous else None,
                "current": self.mask_token(value),
            })
            data["settings_history"] = history[-50:]
            self._write(data)
            return {
                "key": key,
                "previous_masked": self.mask_token(str(previous)) if previous else None,
                "current_masked": self.mask_token(value),
                "changed_at": iso_now(),
            }

    @staticmethod
    def mask_token(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if len(value) <= 10:
            return value[:4] + "****"
        return value[:6] + "****" + value[-4:]

    @staticmethod
    def _target_key(user: Dict[str, Any]) -> str:
        return str(user.get("open_id") or user.get("user_id") or "").strip()
