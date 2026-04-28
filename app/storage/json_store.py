from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class LocalAuthStore:
    """Simple JSON file store for local development.

    Structure:
    {
      "latest_user_key": "ou_xxx",
      "users": {
        "ou_xxx": {
          "user_info": {...},
          "tokens": {...}
        }
      }
    }
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write({"latest_user_key": None, "users": {}})

    def _read(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {"latest_user_key": None, "users": {}}
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def upsert_user(self, user_key: str, *, user_info: Dict[str, Any], tokens: Dict[str, Any]) -> None:
        data = self._read()
        users = data.setdefault("users", {})
        users[user_key] = {
            "user_info": user_info,
            "tokens": tokens,
        }
        data["latest_user_key"] = user_key
        self._write(data)

    def update_tokens(self, user_key: str, tokens: Dict[str, Any]) -> None:
        data = self._read()
        users = data.setdefault("users", {})
        if user_key not in users:
            raise KeyError(f"本地未找到用户 {user_key}")
        users[user_key]["tokens"] = tokens
        data["latest_user_key"] = user_key
        self._write(data)

    def get_user(self, user_key: str) -> Optional[Dict[str, Any]]:
        return self._read().get("users", {}).get(user_key)

    def get_latest_user(self) -> Optional[Dict[str, Any]]:
        data = self._read()
        latest_user_key = data.get("latest_user_key")
        if not latest_user_key:
            return None
        user_record = data.get("users", {}).get(latest_user_key)
        if not user_record:
            return None
        return {"user_key": latest_user_key, **user_record}

    def list_users(self) -> Dict[str, Any]:
        return self._read().get("users", {})

    def find_users_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Find users by exact display name (case-insensitive)."""
        target = (name or "").strip().casefold()
        if not target:
            return []

        matched: List[Dict[str, Any]] = []
        data = self._read()
        latest_user_key = data.get("latest_user_key")
        users = data.get("users", {})

        for user_key, record in users.items():
            user_info = record.get("user_info", {})
            display_name = str(user_info.get("name") or "").strip()
            if display_name.casefold() == target:
                matched.append({
                    "user_key": user_key,
                    "is_latest": user_key == latest_user_key,
                    **record,
                })
        return matched
