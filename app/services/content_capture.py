from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from app.config import Settings
from app.services.feishu_docx import FeishuDocxService
from app.services.feishu_oauth import FeishuOAuthService
from app.services.feishu_search import FeishuSearchService
from app.storage.capture_store import CaptureStore
from app.utils.time_utils import iso_now

logger = logging.getLogger(__name__)


class ContentCaptureService:
    """Capture new recording transcript docs for selected contact users."""

    TOKEN_FIELDS = ("token", "docs_token", "doc_token", "obj_token", "document_id", "file_token")

    def __init__(
        self,
        settings: Settings,
        capture_store: CaptureStore,
        oauth_service: FeishuOAuthService,
        search_service: FeishuSearchService,
        docx_service: FeishuDocxService,
    ):
        self.settings = settings
        self.capture_store = capture_store
        self.oauth_service = oauth_service
        self.search_service = search_service
        self.docx_service = docx_service
        self._run_lock = threading.Lock()
        self._running = False
        self._scheduler_started = False

    def list_targets(self) -> List[Dict[str, Any]]:
        return self.capture_store.list_targets()

    def add_target(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return self.capture_store.upsert_target(user)

    def delete_target(self, target_key: str) -> bool:
        return self.capture_store.delete_target(target_key)

    def list_runs(self) -> List[Dict[str, Any]]:
        return self.capture_store.list_runs()

    def run_capture(self, *, user_key: Optional[str] = None) -> Dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {
                "ok": False,
                "message": "capture is already running",
                "targets": [],
                "created": 0,
                "skipped": 0,
                "failed": 0,
            }

        self._running = True
        started_at = iso_now()
        started_monotonic = time.monotonic()
        target_folder_token = self.target_folder_token()
        targets = self.capture_store.list_targets()
        interval_seconds = getattr(self.settings, "capture_target_interval_seconds", 1.0)
        created_count = 0
        skipped_count = 0
        failed_count = 0
        search_group_count = 0
        files_examined = 0
        target_results: List[Dict[str, Any]] = []

        try:
            fallback_user_key = user_key or self._default_auth_user_key()
            if not target_folder_token:
                raise RuntimeError("CAPTURE_TARGET_FOLDER_TOKEN is required before running capture")

            # Group targets by the token that will actually be used, so each
            # token searches the keyword ONCE instead of once per target —
            # the single biggest API-load reduction for many targets.
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for target in targets:
                group_key = self._resolve_target_user_key(target) or fallback_user_key
                groups.setdefault(group_key, []).append(target)

            logger.info(
                "capture run started: targets=%d groups=%d interval=%.1fs fallback_user=%s",
                len(targets),
                len(groups),
                interval_seconds,
                fallback_user_key,
            )

            for group_index, (group_key, group_targets) in enumerate(groups.items()):
                # Pace between token groups as well.
                if group_index > 0 and interval_seconds > 0:
                    time.sleep(interval_seconds)

                # Group-level isolation: token refresh / search failures only
                # affect the targets inside this group.
                try:
                    session_record = self.oauth_service.ensure_valid_access_token(group_key)
                    access_token = session_record["tokens"]["access_token"]
                    group_files = self.search_service.search_docs(
                        access_token=access_token,
                        keyword=self.settings.capture_search_keyword,
                        docs_types=["doc", "docx"],
                        count=50,
                        max_pages=4,
                    )
                    search_group_count += 1
                    files_by_owner: Dict[str, List[Dict[str, Any]]] = {}
                    for file in group_files:
                        owner = str(file.get("owner_id") or "").strip()
                        if owner:
                            files_by_owner.setdefault(owner, []).append(file)
                    logger.info(
                        "capture group searched: auth_user=%s files=%d owners=%d",
                        session_record["user_key"],
                        len(group_files),
                        len(files_by_owner),
                    )
                except Exception as exc:  # noqa: BLE001
                    failed_count += len(group_targets)
                    logger.warning(
                        "capture group failed: auth_user_key=%s targets=%d error=%s",
                        group_key,
                        len(group_targets),
                        exc,
                    )
                    for target in group_targets:
                        target_results.append({
                            "target_key": target.get("target_key"),
                            "name": target.get("name"),
                            "created": 0,
                            "skipped": 0,
                            "failed": 1,
                            "error": str(exc),
                            "items": [],
                        })
                    continue

                for target_index, target in enumerate(group_targets):
                    # Pace requests to reduce the chance of hitting Feishu API rate limits.
                    if target_index > 0 and interval_seconds > 0:
                        time.sleep(interval_seconds)

                    # Files are already partitioned by owner at group level;
                    # this is also the reliable local owner filter (the search
                    # API silently ignores invalid owner_ids).
                    owner_id = str(
                        target.get("open_id") or target.get("user_id") or target.get("target_key") or ""
                    ).strip()
                    files = files_by_owner.get(owner_id, [])
                    files_examined += len(files)

                    # Per-target isolation: one broken target (e.g. expired refresh_token)
                    # must not abort the whole run; log it and keep going.
                    try:
                        result = self._capture_target(
                            access_token=access_token,
                            target=target,
                            target_folder_token=target_folder_token,
                            files=files,
                        )
                        result["auth_user_key"] = session_record["user_key"]
                    except Exception as exc:  # noqa: BLE001
                        failed_count += 1
                        logger.warning(
                            "capture target failed: target_key=%s name=%s error=%s",
                            target.get("target_key"),
                            target.get("name"),
                            exc,
                        )
                        result = {
                            "target_key": target.get("target_key"),
                            "name": target.get("name"),
                            "created": 0,
                            "skipped": 0,
                            "failed": 1,
                            "error": str(exc),
                            "items": [],
                        }

                    created_count += result["created"]
                    skipped_count += result["skipped"]
                    failed_count += result["failed"]
                    target_results.append(result)
                    logger.info(
                        "capture target done: target_key=%s name=%s searched=%s created=%s skipped=%s failed=%s",
                        target.get("target_key"),
                        target.get("name"),
                        result.get("searched", 0),
                        result.get("created", 0),
                        result.get("skipped", 0),
                        result.get("failed", 0),
                    )

            duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            run = self.capture_store.append_run({
                "ok": True,
                "started_at": started_at,
                "finished_at": iso_now(),
                "duration_ms": duration_ms,
                "fallback_user_key": fallback_user_key,
                "target_count": len(targets),
                "search_group_count": search_group_count,
                "files_examined": files_examined,
                "created": created_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "has_target_folder": bool(target_folder_token),
                "targets": target_results,
            })
            logger.info(
                "capture run finished: targets=%d groups=%d created=%d skipped=%d failed=%d duration_ms=%d",
                len(targets),
                search_group_count,
                created_count,
                skipped_count,
                failed_count,
                duration_ms,
            )
            return {
                "ok": True,
                **run,
            }
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            duration_ms = int((time.monotonic() - started_monotonic) * 1000)
            logger.error("capture run aborted: %s", exc, exc_info=True)
            run = self.capture_store.append_run({
                "ok": False,
                "started_at": started_at,
                "finished_at": iso_now(),
                "duration_ms": duration_ms,
                "target_count": len(targets),
                "created": created_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "error": str(exc),
                "targets": target_results,
            })
            return {
                "ok": False,
                **run,
            }
        finally:
            self._running = False
            self._run_lock.release()

    def start_capture_async(self, *, user_key: Optional[str] = None) -> Dict[str, Any]:
        """Kick off a capture run in a background thread; return immediately."""
        if self._running or self._run_lock.locked():
            return {"started": False, "message": "capture is already running"}
        thread = threading.Thread(
            target=self._safe_run_capture,
            args=(user_key,),
            name="content-capture-manual",
            daemon=True,
        )
        thread.start()
        return {"started": True, "message": "capture started"}

    def is_running(self) -> bool:
        return bool(self._running)

    def capture_status(self) -> Dict[str, Any]:
        """Lightweight status for monitoring: running flag + recent run health."""
        runs = self.capture_store.list_runs()
        consecutive_failures = 0
        last_success_at = None
        for run in runs:
            ok = run.get("ok")
            if ok is None:
                ok = not run.get("error")
            if ok:
                last_success_at = run.get("started_at")
                break
            consecutive_failures += 1

        last_run = runs[0] if runs else None
        summary = None
        if last_run:
            summary = {
                "run_started_at": last_run.get("started_at"),
                "ok": bool(last_run.get("ok", not last_run.get("error"))),
                "target_count": last_run.get("target_count"),
                "created": last_run.get("created"),
                "skipped": last_run.get("skipped"),
                "failed": last_run.get("failed"),
                "duration_ms": last_run.get("duration_ms"),
                "error": last_run.get("error"),
            }
        return {
            "running": self.is_running(),
            "consecutive_failures": consecutive_failures,
            "last_success_at": last_success_at,
            "last_run": summary,
        }

    def start_scheduler(self) -> None:
        if self._scheduler_started:
            return
        self._scheduler_started = True
        thread = threading.Thread(target=self._scheduler_loop, name="content-capture-scheduler", daemon=True)
        thread.start()

    def _scheduler_loop(self) -> None:
        if self.settings.capture_startup_refresh:
            self._safe_run_capture()

        interval = max(int(self.settings.capture_refresh_seconds or 0), 60)
        while True:
            threading.Event().wait(interval)
            self._safe_run_capture()

    def _safe_run_capture(self, user_key: Optional[str] = None) -> None:
        try:
            self.run_capture(user_key=user_key)
        except Exception:
            return

    def _capture_target(
        self,
        *,
        access_token: str,
        target: Dict[str, Any],
        target_folder_token: str,
        files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        created_count = 0
        skipped_count = 0
        failed_count = 0
        for file in files:
            token = self._file_token(file)
            if not token:
                skipped_count += 1
                items.append({"ok": False, "skipped": True, "reason": "missing token", "file": file})
                continue

            title = str(file.get("title") or file.get("name") or "").strip()
            if "文字记录" not in title:
                skipped_count += 1
                items.append({"ok": True, "skipped": True, "reason": "title filter mismatch", "token": token, "title": title})
                continue

            file_key = f"{target.get('target_key')}:{token}"
            if self.capture_store.get_processed(file_key):
                skipped_count += 1
                items.append({"ok": True, "skipped": True, "reason": "already processed", "token": token})
                continue

            try:
                content = self.docx_service.get_raw_content(access_token, token)
                title = self._build_capture_title(target, content)
                created_document = None
                if target_folder_token:
                    created_document = self.docx_service.clone_plain_text(
                        access_token=access_token,
                        source_document_id=token,
                        target_folder_token=target_folder_token,
                        title=title,
                    )

                saved = self.capture_store.mark_processed(file_key, {
                    "target_key": target.get("target_key"),
                    "target_name": target.get("name"),
                    "source_token": token,
                    "source_title": file.get("title") or file.get("name") or "",
                    "capture_title": title,
                    "created_document": created_document,
                    "raw_content_length": len(content),
                })
                created_count += 1
                items.append({"ok": True, **saved})
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                logger.warning(
                    "capture file failed: target=%s token=%s error=%s",
                    target.get("name") or target.get("target_key"),
                    token,
                    exc,
                )
                items.append({"ok": False, "token": token, "error": str(exc)})

        return {
            "target_key": target.get("target_key"),
            "name": target.get("name"),
            "searched": len(files),
            "created": created_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "items": items,
        }

    def _default_auth_user_key(self) -> str:
        users = self.oauth_service.store.list_users()
        if not users:
            raise RuntimeError("no authorized user available for capture")
        return next(iter(users.keys()))

    def target_folder_token(self) -> str:
        """Resolve capture target folder token: frontend override first, then env."""
        override = self.capture_store.get_setting("capture_target_folder_token")
        if override and override.strip():
            return override.strip()
        return (self.settings.capture_target_folder_token or "").strip()

    def target_folder_token_status(self) -> Dict[str, Any]:
        override = (self.capture_store.get_setting("capture_target_folder_token") or "").strip()
        env_value = (self.settings.capture_target_folder_token or "").strip()
        if override:
            return {
                "configured": True,
                "source": "frontend",
                "masked_token": self.capture_store.mask_token(override),
            }
        if env_value:
            return {
                "configured": True,
                "source": "env",
                "masked_token": self.capture_store.mask_token(env_value),
            }
        return {"configured": False, "source": None, "masked_token": None}

    def _resolve_target_user_key(self, target: Dict[str, Any]) -> Optional[str]:
        """Return the target's user_key if they have a local OAuth session, else None."""
        candidate_keys = [
            target.get("open_id"),
            target.get("user_id"),
            target.get("union_id"),
        ]
        users = self.oauth_service.store.list_users()
        for key in candidate_keys:
            key = str(key or "").strip()
            if key and key in users:
                return key
        return None

    @classmethod
    def _file_token(cls, file: Dict[str, Any]) -> str:
        for field in cls.TOKEN_FIELDS:
            value = str(file.get(field) or "").strip()
            if value:
                return value
        return ""

    def _build_capture_title(self, target: Dict[str, Any], content: str) -> str:
        name = self._safe_title_part(str(target.get("name") or target.get("en_name") or "unknown"))
        stamp = self._extract_recording_stamp(content) or "unknown_time"
        return f"{name}_{stamp}"

    @staticmethod
    def _safe_title_part(value: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value.strip())
        return cleaned.strip("_") or "unknown"

    @staticmethod
    def _extract_recording_stamp(content: str) -> str:
        head = "\n".join(content.splitlines()[:12])
        patterns = [
            r"录音时间[：:]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(\d{1,2})[:：](\d{2})",
            r"录制时间[：:]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(\d{1,2})[:：](\d{2})",
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2}).*?(\d{1,2})[:：](\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, head, flags=re.S)
            if match:
                year, month, day, hour, minute = match.groups()[:5]
                return f"{year}{month.zfill(2)}{day.zfill(2)}_{hour.zfill(2)}{minute}"
        return ""
