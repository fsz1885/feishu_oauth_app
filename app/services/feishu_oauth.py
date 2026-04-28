from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlencode

import requests

from app.config import Settings
from app.storage.json_store import LocalAuthStore
from app.utils.time_utils import expires_at_from_seconds, is_expired, iso_now


class FeishuOAuthService:
    """OAuth, token refresh, and user info retrieval."""

    def __init__(self, settings: Settings, store: LocalAuthStore):
        self.settings = settings
        self.store = store

    def build_auth_url(self) -> str:
        params = {
            "client_id": self.settings.app_id,
            "redirect_uri": self.settings.redirect_uri,
            "response_type": "code",
            "scope": self.settings.scope_string,
        }
        return f"{self.settings.auth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> Dict[str, Any]:
        body = {
            "grant_type": "authorization_code",
            "client_id": self.settings.app_id,
            "client_secret": self.settings.app_secret,
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }
        result = self._post_json(self.settings.token_url, body)
        return self._normalize_token_payload(result)

    def refresh_user_token(self, refresh_token: str) -> Dict[str, Any]:
        body = {
            "grant_type": "refresh_token",
            "client_id": self.settings.app_id,
            "client_secret": self.settings.app_secret,
            "refresh_token": refresh_token,
        }
        result = self._post_json(self.settings.refresh_token_url, body)
        return self._normalize_token_payload(result)

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(self.settings.user_info_url, headers=headers, timeout=30)
        try:
            result = resp.json()
        except ValueError:
            raise RuntimeError(f"获取用户信息失败：返回非 JSON，HTTP={resp.status_code}, body={resp.text}")
        if resp.status_code != 200 or result.get("code") != 0:
            raise RuntimeError(f"获取用户信息失败：HTTP={resp.status_code}, result={result}")
        return result.get("data", {})

    def persist_user_session(self, token_payload: Dict[str, Any], user_info: Dict[str, Any]) -> str:
        user_key = self._get_user_key(user_info)
        record_tokens = {
            **token_payload,
            "saved_at": iso_now(),
        }
        self.store.upsert_user(user_key, user_info=user_info, tokens=record_tokens)
        return user_key

    def ensure_valid_access_token(
        self,
        user_key: str,
    ) -> Dict[str, Any]:
        """Get a usable access token for the explicitly selected user."""
        user_record = self._get_user_record(user_key)

        tokens = user_record["tokens"]
        if not is_expired(tokens.get("access_token_expires_at")):
            return user_record

        return self.refresh_access_token(user_key)

    def refresh_access_token(self, user_key: str) -> Dict[str, Any]:
        """Refresh and persist the access token for the explicitly selected user."""
        user_record = self._get_user_record(user_key)
        tokens = user_record["tokens"]

        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("本地没有 refresh_token，请重新授权")
        if is_expired(tokens.get("refresh_token_expires_at"), skew_seconds=300):
            raise RuntimeError("refresh_token 已过期，请重新授权")

        refreshed = self.refresh_user_token(refresh_token)
        refreshed["scope"] = refreshed.get("scope") or tokens.get("scope")
        refreshed["refresh_token"] = refreshed.get("refresh_token") or refresh_token
        refreshed["refresh_token_expires_at"] = (
            refreshed.get("refresh_token_expires_at") or tokens.get("refresh_token_expires_at")
        )
        refreshed["refresh_token_expires_in"] = (
            refreshed.get("refresh_token_expires_in") or tokens.get("refresh_token_expires_in")
        )
        refreshed["user_key"] = user_record["user_key"]
        refreshed["saved_at"] = iso_now()
        self.store.update_tokens(user_record["user_key"], refreshed)
        return {
            "user_key": user_record["user_key"],
            "user_info": user_record["user_info"],
            "tokens": refreshed,
        }

    def _get_user_record(self, user_key: str) -> Dict[str, Any]:
        if not user_key:
            raise RuntimeError("user_key is required")

        record = self.store.get_user(user_key)
        if not record:
            raise RuntimeError(f"本地未找到用户 {user_key}")
        return {"user_key": user_key, **record}

    def _post_json(self, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        try:
            result = resp.json()
        except ValueError:
            raise RuntimeError(f"请求失败：返回非 JSON，HTTP={resp.status_code}, body={resp.text}")
        if resp.status_code != 200 or result.get("code") != 0:
            raise RuntimeError(f"请求失败：HTTP={resp.status_code}, result={result}")
        return result

    def _normalize_token_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "access_token": result.get("access_token"),
            "expires_in": result.get("expires_in"),
            "access_token_expires_at": expires_at_from_seconds(result.get("expires_in")),
            "refresh_token": result.get("refresh_token"),
            "refresh_token_expires_in": result.get("refresh_token_expires_in"),
            "refresh_token_expires_at": expires_at_from_seconds(result.get("refresh_token_expires_in")),
            "token_type": result.get("token_type"),
            "scope": result.get("scope"),
        }

    @staticmethod
    def _get_user_key(user_info: Dict[str, Any]) -> str:
        for key in ["open_id", "user_id", "union_id", "sub"]:
            value = user_info.get(key)
            if value:
                return str(value)
        raise RuntimeError(f"无法从用户信息中识别唯一用户标识: {user_info}")
