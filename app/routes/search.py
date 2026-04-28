from __future__ import annotations

from flask import Blueprint, current_app, request

from app.utils.response import err, ok

bp = Blueprint("search", __name__)


@bp.get("/search")
def search():
    oauth_service = current_app.extensions["oauth_service"]
    search_service = current_app.extensions["search_service"]

    keyword = request.args.get("q", "").strip()
    if not keyword:
        return err("请传入 q，例如 /search?q=项目", 400)

    docs_types_str = request.args.get("docs_types", "").strip()
    docs_types = [x.strip() for x in docs_types_str.split(",") if x.strip()] if docs_types_str else None

    if request.args.get("name", "").strip():
        return err("Search requires user_key. The name argument is no longer supported.", 400)

    user_key = request.args.get("user_key", "").strip()
    if not user_key:
        return err("Search requires user_key. Please choose an authorized user.", 400)

    try:
        session_record = oauth_service.ensure_valid_access_token(
            user_key=user_key,
        )
        files = search_service.search_docs(
            access_token=session_record["tokens"]["access_token"],
            keyword=keyword,
            docs_types=docs_types,
            count=50,
            max_pages=4,
        )
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    return ok(
        keyword=keyword,
        user_key=session_record["user_key"],
        user_name=session_record.get("user_info", {}).get("name"),
        token_scope=session_record["tokens"].get("scope"),
        refreshed_until=session_record["tokens"].get("access_token_expires_at"),
        count=len(files),
        files=files,
    )
