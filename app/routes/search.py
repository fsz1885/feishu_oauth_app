from __future__ import annotations

from flask import Blueprint, current_app, request

from app.utils.response import err, ok

bp = Blueprint("search", __name__)

DOCX_LINK_BASE_URL = "https://gemdalesh.feishu.cn/docx"
TOKEN_FIELDS = ("token", "docs_token", "doc_token", "obj_token", "document_id", "file_token")


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

    # 仅显示该用户名下的文件：默认开启；传 owner_only=false/0 关闭
    # 请求侧传 owner_ids，返回侧本地兜底过滤
    # （搜索接口对 owner_ids 不保证生效，可能返回别人共享的文档）
    owner_only_raw = request.args.get("owner_only", "1").strip().lower()
    owner_only = owner_only_raw not in ("0", "false", "no")

    try:
        session_record = oauth_service.ensure_valid_access_token(
            user_key=user_key,
        )
        files = search_service.search_docs(
            access_token=session_record["tokens"]["access_token"],
            keyword=keyword,
            docs_types=docs_types,
            owner_ids=[user_key] if owner_only else None,
            count=50,
            max_pages=4,
        )
        total_before_owner_filter = len(files)
        files = [_with_docx_link(file) for file in files]
        for file in files:
            file["is_owner"] = str(file.get("owner_id") or "").strip() == user_key
        if owner_only:
            files = [file for file in files if file["is_owner"]]
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    return ok(
        keyword=keyword,
        user_key=session_record["user_key"],
        user_name=session_record.get("user_info", {}).get("name"),
        token_scope=session_record["tokens"].get("scope"),
        refreshed_until=session_record["tokens"].get("access_token_expires_at"),
        owner_filter_applied=owner_only,
        total_before_owner_filter=total_before_owner_filter,
        count=len(files),
        files=files,
    )


def _with_docx_link(file: dict) -> dict:
    enriched = dict(file)
    token = _extract_token(enriched)
    if token and not enriched.get("url"):
        enriched["url"] = f"{DOCX_LINK_BASE_URL}/{token}"
    return enriched


def _extract_token(file: dict) -> str:
    for field in TOKEN_FIELDS:
        value = str(file.get(field) or "").strip()
        if value:
            return value
    return ""
