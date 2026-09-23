from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, current_app, request

from app.utils.response import err, ok

bp = Blueprint("capture", __name__)
logger = logging.getLogger(__name__)


@bp.get("/capture/targets")
def list_targets():
    capture_service = current_app.extensions["capture_service"]
    targets = capture_service.list_targets()
    return ok(count=len(targets), targets=targets)


@bp.post("/capture/targets")
def add_target():
    capture_service = current_app.extensions["capture_service"]
    payload = request.get_json(silent=True) or {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload

    try:
        target = capture_service.add_target(user)
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 400)

    return ok(message="capture target saved", target=target)


@bp.delete("/capture/targets/<target_key>")
def delete_target(target_key: str):
    capture_service = current_app.extensions["capture_service"]
    deleted = capture_service.delete_target(target_key)
    return ok(deleted=deleted, target_key=target_key)


@bp.post("/capture/run")
def run_capture():
    capture_service = current_app.extensions["capture_service"]
    payload = request.get_json(silent=True) or {}
    user_key = str(payload.get("user_key") or request.form.get("user_key") or "").strip() or None
    result = capture_service.run_capture(user_key=user_key)
    if not result.get("ok"):
        return err(result.get("error") or result.get("message") or "capture failed", 500, result=result)
    return ok(message="capture finished", result=result)


@bp.get("/capture/runs")
def list_runs():
    capture_service = current_app.extensions["capture_service"]
    runs = capture_service.list_runs()
    return ok(count=len(runs), runs=runs)


@bp.get("/capture/failures")
def list_failures():
    """Flatten recent capture failures (run-level, target-level, file-level) for admins."""
    capture_service = current_app.extensions["capture_service"]
    try:
        limit = max(1, min(int(request.args.get("limit", 5)), 20))
    except (TypeError, ValueError):
        limit = 5

    runs_with_failures = []
    for run in capture_service.list_runs():
        failures = []

        if run.get("error"):
            failures.append({
                "scope": "run",
                "target_name": "整轮抓取",
                "error": run["error"],
            })

        for target in run.get("targets", []):
            target_name = target.get("name") or target.get("target_key") or "未知目标"
            if target.get("error"):
                failures.append({
                    "scope": "target",
                    "target_name": target_name,
                    "error": target["error"],
                })
            for item in target.get("items", []):
                if item.get("ok") is False and not item.get("skipped"):
                    failures.append({
                        "scope": "file",
                        "target_name": target_name,
                        "token": item.get("token") or "",
                        "title": item.get("source_title") or item.get("title") or "",
                        "error": item.get("error") or "unknown error",
                    })

        if failures:
            runs_with_failures.append({
                "run_started_at": run.get("started_at"),
                "run_finished_at": run.get("finished_at"),
                "summary": (
                    f"targets={run.get('target_count', 0)} "
                    f"created={run.get('created', 0)} "
                    f"skipped={run.get('skipped', 0)} "
                    f"failed={run.get('failed', 0)}"
                ),
                "failures": failures,
            })
        if len(runs_with_failures) >= limit:
            break

    return ok(count=len(runs_with_failures), runs_with_failures=runs_with_failures)


@bp.get("/capture/settings")
def get_capture_settings():
    """Return the effective capture target folder token (masked) and its source."""
    capture_service = current_app.extensions["capture_service"]
    return ok(**capture_service.target_folder_token_status())


@bp.post("/capture/settings/folder-token")
def update_capture_folder_token():
    """Validate a new target folder token via Feishu, then persist it as override.

    Guard rails: explicit confirm flag, strict format check, and a live
    validation that creates a throwaway test document in the target folder.
    The setting is only saved when the Feishu API accepts the folder token.
    """
    capture_service = current_app.extensions["capture_service"]
    oauth_service = current_app.extensions["oauth_service"]
    docx_service = current_app.extensions["docx_service"]
    payload = request.get_json(silent=True) or {}

    folder_token = str(payload.get("folder_token") or "").strip()
    confirm = payload.get("confirm") is True

    if not confirm:
        return err("请先勾选确认复选框后再提交", 400)
    if not folder_token:
        return err("folder_token 不能为空", 400)
    if not folder_token.startswith("fld") or len(folder_token) < 10:
        return err("folder_token 格式不正确：应以 fld 开头且长度不小于 10", 400)

    users = oauth_service.store.list_users()
    if not users:
        return err("本地没有已授权用户，无法验证文件夹 token，请先完成 OAuth 授权", 400)
    user_key = next(iter(users.keys()))

    test_title = f"【验证用-可删除】token校验_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        session_record = oauth_service.ensure_valid_access_token(user_key)
        access_token = session_record["tokens"]["access_token"]
        created = docx_service.create_document(
            access_token=access_token,
            target_folder_token=folder_token,
            title=test_title,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("folder token validation failed: %s", exc)
        return err(f"飞书校验失败，设置未保存：{exc}", 400)

    result = capture_service.capture_store.set_setting(
        "capture_target_folder_token", folder_token, changed_by="frontend"
    )
    logger.info(
        "capture folder token updated via frontend: %s -> %s",
        result.get("previous_masked"),
        result.get("current_masked"),
    )
    return ok(
        message="目标文件夹 token 已通过飞书校验并保存",
        test_document={
            "document_id": created.get("document_id"),
            "title": test_title,
            "hint": "验证用的测试文档已创建在目标文件夹中，请打开文件夹手动删除它",
        },
        **result,
    )
