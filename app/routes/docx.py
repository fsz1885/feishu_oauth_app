from __future__ import annotations

from flask import Blueprint, current_app, request

from app.utils.response import err, ok

bp = Blueprint("docx", __name__)


@bp.post("/docx/clone-plain-text")
def clone_plain_text():
    oauth_service = current_app.extensions["oauth_service"]
    docx_service = current_app.extensions["docx_service"]
    payload = request.get_json(silent=True) or {}

    user_key = str(payload.get("user_key") or request.form.get("user_key") or "").strip()
    source_document_id = _extract_document_id(str(
        payload.get("source_document_id") or request.form.get("source_document_id") or ""
    ).strip())
    target_folder_token = str(
        payload.get("target_folder_token") or request.form.get("target_folder_token") or ""
    ).strip()
    title = str(payload.get("title") or request.form.get("title") or "").strip()

    if not user_key:
        return err("user_key is required", 400)
    if not source_document_id:
        return err("source_document_id is required", 400)
    if not target_folder_token:
        return err("target_folder_token is required", 400)

    try:
        session_record = oauth_service.ensure_valid_access_token(user_key=user_key)
        result = docx_service.clone_plain_text(
            access_token=session_record["tokens"]["access_token"],
            source_document_id=source_document_id,
            target_folder_token=target_folder_token,
            title=title or None,
        )
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    return ok(
        message="document cloned as plain text",
        user_key=session_record["user_key"],
        user_name=session_record.get("user_info", {}).get("name"),
        **result,
    )


def _extract_document_id(value: str) -> str:
    if "/docx/" not in value:
        return value

    document_id = value.split("/docx/", 1)[1]
    for separator in ["?", "#", "/"]:
        document_id = document_id.split(separator, 1)[0]
    return document_id.strip()
