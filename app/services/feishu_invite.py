from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

import requests

from app.config import Settings
from app.utils.time_utils import iso_now


class FeishuInviteService:
    """Search visible contacts and send OAuth invitation messages."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache_lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._cached_users: List[Dict[str, Any]] = []
        self._cache_meta: Dict[str, Any] = self._empty_meta()
        self._cache_error: Optional[str] = None
        self._cache_refreshed_at: Optional[str] = None
        self._cache_refreshing = False
        self._scheduler_started = False

    def search_users(self, keyword: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        return self.search_users_with_meta(keyword, limit=limit)["users"]

    def search_users_with_meta(self, keyword: str, *, limit: int = 20) -> Dict[str, Any]:
        keyword = (keyword or "").strip()
        if not keyword:
            return {"users": [], "meta": self._empty_meta()}

        with self._cache_lock:
            cached_users = list(self._cached_users)
            cache_meta = dict(self._cache_meta)

        if not cached_users:
            self.refresh_contact_cache()
            with self._cache_lock:
                cached_users = list(self._cached_users)
                cache_meta = dict(self._cache_meta)

        if cached_users:
            matched = [user for user in cached_users if self._matches_keyword(user, keyword)]
            meta = dict(cache_meta)
            meta.update({
                "matched_fields": ["name", "en_name", "email", "mobile", "user_id", "open_id", "union_id"],
                "cache_hit": True,
                "matched_count": len(matched),
            })
            return {"users": matched[:limit], "meta": meta}

        return self._search_users_live(keyword, limit=limit)

    def list_cached_contacts(self, *, limit: Optional[int] = None, offset: int = 0) -> Dict[str, Any]:
        with self._cache_lock:
            users = list(self._cached_users)
            meta = dict(self._cache_meta)
            error = self._cache_error
            refreshed_at = self._cache_refreshed_at
            refreshing = self._cache_refreshing

        total = len(users)
        if offset < 0:
            offset = 0
        if limit is not None:
            users = users[offset:offset + limit]
        else:
            users = users[offset:]

        meta.update({
            "cache_hit": True,
            "cache_error": error,
            "cache_refreshed_at": refreshed_at,
            "cache_refreshing": refreshing,
            "total_cached_user_count": total,
        })
        return {"users": users, "meta": meta}

    def refresh_contact_cache(self) -> Dict[str, Any]:
        self._refresh_lock.acquire()

        with self._cache_lock:
            self._cache_refreshing = True

        try:
            result = self._fetch_all_visible_contacts()
            with self._cache_lock:
                self._cached_users = result["users"]
                self._cache_meta = result["meta"]
                self._cache_error = None
                self._cache_refreshed_at = iso_now()
            return self.list_cached_contacts()
        except Exception as exc:  # noqa: BLE001
            with self._cache_lock:
                self._cache_error = str(exc)
            raise
        finally:
            with self._cache_lock:
                self._cache_refreshing = False
            self._refresh_lock.release()

    def refresh_contact_cache_async(self) -> None:
        thread = threading.Thread(target=self._safe_refresh_contact_cache, name="feishu-contact-cache-refresh", daemon=True)
        thread.start()

    def start_contact_cache_scheduler(self) -> None:
        if self._scheduler_started:
            return
        self._scheduler_started = True
        thread = threading.Thread(target=self._contact_cache_scheduler_loop, name="feishu-contact-cache-scheduler", daemon=True)
        thread.start()

    def _safe_refresh_contact_cache(self) -> None:
        try:
            self.refresh_contact_cache()
        except Exception:
            return

    def _contact_cache_scheduler_loop(self) -> None:
        if self.settings.contact_cache_startup_refresh:
            self._safe_refresh_contact_cache()

        interval = max(int(self.settings.contact_cache_refresh_seconds or 0), 60)
        while True:
            threading.Event().wait(interval)
            self._safe_refresh_contact_cache()

    def _search_users_live(self, keyword: str, *, limit: int = 20) -> Dict[str, Any]:
        token = self.get_tenant_access_token()
        scope = self.get_contact_scope(token)
        department_ids = scope.get("department_ids") or []
        scoped_user_ids = scope.get("user_ids") or []

        matched: List[Dict[str, Any]] = []
        samples: List[Dict[str, Any]] = []
        seen_keys = set()
        scanned_user_count = 0
        visited_departments = set()

        for user_id in scoped_user_ids:
            user = self.get_user(token, user_id)
            if not user:
                continue
            summary = self._summarize_user(user)
            scanned_user_count += 1
            self._append_sample(samples, summary)
            unique_key = summary.get("open_id") or summary.get("user_id")
            if unique_key and unique_key not in seen_keys and self._matches_keyword(summary, keyword):
                matched.append(summary)
                seen_keys.add(unique_key)
            if len(matched) >= limit:
                return {
                    "users": matched,
                    "meta": {
                        "scope_department_count": len(department_ids),
                        "scope_user_count": len(scoped_user_ids),
                        "visited_department_count": len(visited_departments),
                        "scanned_user_count": scanned_user_count,
                        "sample_users": samples,
                    },
                }

        for department_id in department_ids:
            for visible_department_id in self.expand_department_ids(token, department_id):
                if visible_department_id in visited_departments:
                    continue
                visited_departments.add(visible_department_id)
                department_users = self.list_department_users(token, visible_department_id)
                for user in department_users:
                    scanned_user_count += 1
                    summary = self._summarize_user(user)
                    self._append_sample(samples, summary)
                    unique_key = summary.get("open_id") or summary.get("user_id")
                    if not unique_key or unique_key in seen_keys:
                        continue
                    if self._matches_keyword(summary, keyword):
                        matched.append(summary)
                        seen_keys.add(unique_key)
                    if len(matched) >= limit:
                        return {
                            "users": matched,
                            "meta": {
                                "scope_department_count": len(department_ids),
                                "scope_user_count": len(scoped_user_ids),
                                "visited_department_count": len(visited_departments),
                                "scanned_user_count": scanned_user_count,
                                "sample_users": samples,
                            },
                        }

        return {
            "users": matched,
            "meta": {
                "scope_department_count": len(department_ids),
                "scope_user_count": len(scoped_user_ids),
                "visited_department_count": len(visited_departments),
                "scanned_user_count": scanned_user_count,
                "sample_users": samples,
                "matched_fields": ["name", "en_name", "email", "mobile", "user_id", "open_id", "union_id"],
            },
        }

    def _fetch_all_visible_contacts(self) -> Dict[str, Any]:
        token = self.get_tenant_access_token()
        scope = self.get_contact_scope(token)
        department_ids = scope.get("department_ids") or []
        scoped_user_ids = scope.get("user_ids") or []

        users: List[Dict[str, Any]] = []
        samples: List[Dict[str, Any]] = []
        seen_keys = set()
        scanned_user_count = 0
        visited_departments = set()

        for user_id in scoped_user_ids:
            user = self.get_user(token, user_id)
            if not user:
                continue
            scanned_user_count += 1
            summary = self._summarize_user(user)
            self._append_sample(samples, summary)
            unique_key = summary.get("open_id") or summary.get("user_id")
            if unique_key and unique_key not in seen_keys:
                users.append(summary)
                seen_keys.add(unique_key)

        for department_id in department_ids:
            for visible_department_id in self.expand_department_ids(token, department_id):
                if visible_department_id in visited_departments:
                    continue
                visited_departments.add(visible_department_id)
                for user in self.list_department_users(token, visible_department_id):
                    scanned_user_count += 1
                    summary = self._summarize_user(user)
                    self._append_sample(samples, summary)
                    unique_key = summary.get("open_id") or summary.get("user_id")
                    if unique_key and unique_key not in seen_keys:
                        users.append(summary)
                        seen_keys.add(unique_key)

        users.sort(key=lambda item: (str(item.get("name") or ""), str(item.get("open_id") or "")))
        return {
            "users": users,
            "meta": {
                "scope_department_count": len(department_ids),
                "scope_user_count": len(scoped_user_ids),
                "visited_department_count": len(visited_departments),
                "scanned_user_count": scanned_user_count,
                "sample_users": samples,
                "total_visible_user_count": len(users),
                "users_with_name_count": sum(1 for user in users if user.get("name")),
                "users_with_email_count": sum(1 for user in users if user.get("email")),
                "users_with_mobile_count": sum(1 for user in users if user.get("mobile")),
                "matched_fields": ["name", "en_name", "email", "mobile", "user_id", "open_id", "union_id"],
            },
        }

    def expand_department_ids(self, token: str, department_id: str) -> List[str]:
        department_ids = [department_id]
        page_token = ""
        while True:
            result = self._request_json(
                "get",
                f"{self.settings.contact_department_url}/{department_id}/children",
                token=token,
                params={
                    "department_id_type": "open_department_id",
                    "user_id_type": "open_id",
                    "fetch_child": "true",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            data = result.get("data", {}) or {}
            for department in data.get("items") or []:
                child_id = department.get("open_department_id") or department.get("department_id")
                if child_id:
                    department_ids.append(child_id)
            if not data.get("has_more"):
                break
            page_token = data.get("page_token") or ""
            if not page_token:
                break
        return department_ids

    def get_user(self, token: str, user_id: str) -> Dict[str, Any]:
        result = self._request_json(
            "get",
            f"{self.settings.contact_user_url}/{user_id}",
            token=token,
            params={
                "user_id_type": "open_id",
                "department_id_type": "open_department_id",
            },
        )
        return (result.get("data") or {}).get("user") or {}

    def send_auth_invite(
        self,
        *,
        receive_id: str,
        receive_id_type: str,
        auth_url: str,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = self.get_tenant_access_token()
        body = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps(
                {
                    "text": f"{message or '请点击下面的链接完成飞书授权：'}\n{auth_url}",
                },
                ensure_ascii=False,
            ),
        }
        result = self._request_json(
            "post",
            self.settings.send_message_url,
            token=token,
            params={"receive_id_type": receive_id_type},
            json_body=body,
        )
        return {
            "receive_id": receive_id,
            "receive_id_type": receive_id_type,
            "message_id": (result.get("data") or {}).get("message_id"),
            "raw_data": result.get("data") or {},
        }

    def send_invite(self, *, open_id: str, name: str = "", invite_url: str) -> Dict[str, Any]:
        display_name = name or "同事"
        return self.send_auth_invite(
            receive_id=open_id,
            receive_id_type="open_id",
            auth_url=invite_url,
            message=f"{display_name}，请打开下面的链接完成飞书授权，授权成功后我这边就能在工具里选择你的账号进行搜索：",
        )

    def get_tenant_access_token(self) -> str:
        result = self._request_json(
            "post",
            self.settings.tenant_access_token_url,
            json_body={
                "app_id": self.settings.app_id,
                "app_secret": self.settings.app_secret,
            },
        )
        token = result.get("tenant_access_token")
        if not token:
            raise RuntimeError(f"tenant_access_token missing from response: {result}")
        return token

    def get_contact_scope(self, token: str) -> Dict[str, Any]:
        department_ids: List[str] = []
        user_ids: List[str] = []
        page_token = ""
        while True:
            result = self._request_json(
                "get",
                self.settings.contact_scope_url,
                token=token,
                params={
                    "department_id_type": "open_department_id",
                    "user_id_type": "open_id",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            data = result.get("data", {}) or {}
            department_ids.extend(data.get("department_ids") or data.get("departments") or [])
            user_ids.extend(data.get("user_ids") or data.get("users") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token") or ""
            if not page_token:
                break

        return {
            "department_ids": list(dict.fromkeys(department_ids)),
            "user_ids": list(dict.fromkeys(user_ids)),
        }

    def list_department_users(self, token: str, department_id: str) -> List[Dict[str, Any]]:
        users: List[Dict[str, Any]] = []
        page_token = ""
        while True:
            result = self._request_json(
                "get",
                self.settings.contact_department_users_url,
                token=token,
                params={
                    "department_id": department_id,
                    "department_id_type": "open_department_id",
                    "user_id_type": "open_id",
                    "page_size": 50,
                    "page_token": page_token,
                },
            )
            data = result.get("data", {}) or {}
            users.extend(data.get("items") or data.get("users") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token") or ""
            if not page_token:
                break
        return users

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=30,
        )
        try:
            result = resp.json()
        except ValueError:
            raise RuntimeError(f"Feishu invite request returned non-JSON: HTTP={resp.status_code}, body={resp.text}")

        if resp.status_code != 200 or result.get("code") != 0:
            raise RuntimeError(f"Feishu invite request failed: HTTP={resp.status_code}, result={result}")
        return result

    @staticmethod
    def _summarize_user(user: Dict[str, Any]) -> Dict[str, Any]:
        avatar = user.get("avatar") or {}
        i18n_name = user.get("i18n_name") or {}
        name = (
            user.get("name")
            or i18n_name.get("zh_cn")
            or i18n_name.get("en_us")
            or user.get("nickname")
            or ""
        )
        return {
            "avatar_url": (
                user.get("avatar_url")
                or avatar.get("avatar_72")
                or avatar.get("avatar_240")
                or avatar.get("avatar_origin")
            ),
            "email": user.get("email"),
            "en_name": user.get("en_name") or i18n_name.get("en_us") or "",
            "mobile": user.get("mobile"),
            "name": name,
            "open_id": user.get("open_id"),
            "user_id": user.get("user_id"),
            "union_id": user.get("union_id"),
        }

    @staticmethod
    def _matches_keyword(user: Dict[str, Any], keyword: str) -> bool:
        search_text = " ".join(
            str(user.get(key) or "")
            for key in ["name", "en_name", "email", "mobile", "user_id", "open_id", "union_id"]
        ).casefold()
        return keyword.casefold() in search_text

    @staticmethod
    def _empty_meta() -> Dict[str, int]:
        return {
            "scope_department_count": 0,
            "scope_user_count": 0,
            "visited_department_count": 0,
            "scanned_user_count": 0,
        }

    @staticmethod
    def _append_sample(samples: List[Dict[str, Any]], user: Dict[str, Any]) -> None:
        if len(samples) >= 5:
            return
        samples.append({
            "name": user.get("name"),
            "en_name": user.get("en_name"),
            "avatar_url_present": bool(user.get("avatar_url")),
            "email_present": bool(user.get("email")),
            "mobile_present": bool(user.get("mobile")),
            "user_id": user.get("user_id"),
            "open_id": user.get("open_id"),
        })
