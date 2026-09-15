from __future__ import annotations

from flask import Blueprint, current_app, request

from app.utils.response import err, ok

bp = Blueprint("capture", __name__)


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
