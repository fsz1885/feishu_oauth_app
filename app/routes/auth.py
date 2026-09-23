from __future__ import annotations

from hmac import compare_digest
from html import escape as html_escape

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app.utils.response import err, ok

bp = Blueprint("auth", __name__)


@bp.before_app_request
def require_frontend_password():
    public_endpoints = {
        "auth.frontend_login",
        "auth.invite",
        "auth.login",
        "auth.callback",
        "static",
    }
    if request.endpoint in public_endpoints:
        return None
    if session.get("frontend_authenticated"):
        return None
    if _wants_json_response():
        return err("frontend password required", 401)
    return redirect(url_for("auth.frontend_login", next=request.full_path.rstrip("?")))


@bp.route("/front-login", methods=["GET", "POST"])
def frontend_login():
    next_url = _safe_next_url(request.values.get("next", "/"))
    error_text = ""

    if request.method == "POST":
        settings = current_app.extensions["settings"]
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if compare_digest(username, settings.frontend_username) and compare_digest(
            password, settings.frontend_password
        ):
            session["frontend_authenticated"] = True
            return redirect(next_url)
        error_text = "用户名或密码不正确"

    return render_template("front_login.html", error_text=error_text, next_url=next_url)


@bp.post("/front-logout")
def frontend_logout():
    session.pop("frontend_authenticated", None)
    return redirect(url_for("auth.frontend_login"))


def _safe_next_url(value: str) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def _wants_json_response() -> bool:
    if request.path.startswith(("/search", "/users", "/docx", "/invite/", "/capture")):
        return True
    return request.accept_mimetypes.best == "application/json"


@bp.get("/")
def index():
    oauth_service = current_app.extensions["oauth_service"]
    store = current_app.extensions["store"]
    auth_url = oauth_service.build_auth_url()
    users = store.list_users()
    scope_text = current_app.config["REQUESTED_SCOPE_STRING"]
    settings = current_app.extensions["settings"]
    base_url = settings.public_base_url or request.url_root.rstrip("/")
    invite_url = f"{base_url}/invite"
    invite_text = (
        "请打开下面的链接完成飞书授权，授权成功后我这边就能在工具里选择你的账号进行搜索：\n"
        f"{invite_url}"
    )

    return render_template(
        "index.html",
        users_count=len(users),
        invite_url=invite_url,
        invite_text=invite_text,
        auth_url=auth_url,
        scopes=scope_text.split(),
    )


@bp.get("/invite")
def invite():
    return render_template("invite.html")


@bp.get("/login")
def login():
    oauth_service = current_app.extensions["oauth_service"]
    return redirect(oauth_service.build_auth_url())


@bp.get("/callback")
def callback():
    oauth_service = current_app.extensions["oauth_service"]

    code = request.args.get("code", "").strip()
    error = request.args.get("error", "").strip()

    if error:
        return err("授权失败", 400, args=dict(request.args))
    if not code:
        return err("没有拿到 code", 400, args=dict(request.args))

    try:
        token_payload = oauth_service.exchange_code(code)
        user_info = oauth_service.get_user_info(token_payload["access_token"])
        user_key = oauth_service.persist_user_session(token_payload, user_info)
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    granted_scope = token_payload.get("scope", "")
    payload = {
        "message": "授权成功",
        "user_key": user_key,
        "expires_in": token_payload.get("expires_in"),
        "scope": granted_scope,
        "token_type": token_payload.get("token_type"),
        "has_offline_access": ("offline_access" in granted_scope.split()),
        "has_drive_search_scope": ("drive:drive.search:readonly" in granted_scope.split()),
        "next": "/",
        "user_info": user_info,
    }
    if request.accept_mimetypes.best == "application/json":
        return ok(**payload)
    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>授权成功</title>
      <style>
        body {{
          margin: 0;
          min-height: 100vh;
          display: grid;
          place-items: center;
          font-family: Arial, Helvetica, sans-serif;
          background: #f6f8fb;
          color: #111827;
        }}
        .panel {{
          width: min(520px, calc(100vw - 32px));
          background: white;
          border: 1px solid #dbe3ef;
          border-radius: 12px;
          padding: 28px;
          box-shadow: 0 8px 24px rgba(31, 41, 55, 0.06);
        }}
        h1 {{ margin: 0 0 12px; font-size: 26px; }}
        p {{ margin: 8px 0; color: #4b5563; line-height: 1.7; }}
        code {{
          display: inline-block;
          max-width: 100%;
          word-break: break-all;
          background: #f8fafc;
          border: 1px solid #dbe3ef;
          border-radius: 8px;
          padding: 3px 6px;
          color: #1f2937;
        }}
      </style>
    </head>
    <body>
      <div class="panel">
        <h1>授权成功</h1>
        <p>{html_escape(user_info.get("name") or "你的飞书账号")} 已完成授权，可以关闭这个页面。</p>
        <p>授权标识：<code>{html_escape(user_key)}</code></p>
      </div>
    </body>
    </html>
    """


@bp.get("/users")
def users():
    store = current_app.extensions["store"]
    raw_users = store.list_users()
    summary = []
    for user_key, record in raw_users.items():
        user_info = record.get("user_info", {})
        summary.append({
            "user_key": user_key,
            "name": user_info.get("name"),
            "open_id": user_info.get("open_id"),
            "user_id": user_info.get("user_id"),
        })
    return ok(count=len(summary), users=summary)


@bp.post("/invite/search-users")
def search_invite_users():
    invite_service = current_app.extensions["invite_service"]
    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("q") or request.form.get("q") or "").strip()
    if not keyword:
        return err("q is required", 400)

    try:
        result = invite_service.search_users_with_meta(keyword)
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    users = result["users"]
    return ok(count=len(users), users=users, meta=result["meta"])


@bp.get("/invite/contacts")
def list_invite_contacts():
    invite_service = current_app.extensions["invite_service"]
    limit_arg = request.args.get("limit", "").strip()
    offset_arg = request.args.get("offset", "").strip()
    try:
        limit = int(limit_arg) if limit_arg else None
        offset = int(offset_arg) if offset_arg else 0
    except ValueError:
        return err("limit and offset must be integers", 400)

    result = invite_service.list_cached_contacts(limit=limit, offset=offset)
    return ok(count=len(result["users"]), users=result["users"], meta=result["meta"])


@bp.post("/invite/contacts/refresh")
def refresh_invite_contacts():
    invite_service = current_app.extensions["invite_service"]
    try:
        result = invite_service.refresh_contact_cache()
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    return ok(count=len(result["users"]), users=result["users"], meta=result["meta"])


@bp.post("/invite/send")
def send_invite():
    oauth_service = current_app.extensions["oauth_service"]
    invite_service = current_app.extensions["invite_service"]
    payload = request.get_json(silent=True) or {}
    open_id = str(payload.get("open_id") or request.form.get("open_id") or "").strip()
    name = str(payload.get("name") or request.form.get("name") or "").strip()
    receive_id = str(payload.get("receive_id") or request.form.get("receive_id") or open_id).strip()
    receive_id_type = str(
        payload.get("receive_id_type") or request.form.get("receive_id_type") or "open_id"
    ).strip()
    message = str(payload.get("message") or request.form.get("message") or "").strip()

    if not receive_id:
        return err("receive_id is required", 400)

    try:
        auth_url = oauth_service.build_auth_url()
        invite_message = message or (
            f"{name or '同事'}，请打开下面的链接完成飞书 OAuth 授权。"
            "授权成功后，我这边就能在工具里选择你的账号进行搜索："
        )
        if open_id:
            result = invite_service.send_auth_invite(
                receive_id=open_id,
                receive_id_type="open_id",
                auth_url=auth_url,
                message=invite_message,
            )
            return ok(message="invite sent", open_id=open_id, name=name, auth_url=auth_url, result=result)
        result = invite_service.send_auth_invite(
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            auth_url=auth_url,
            message=invite_message,
        )
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    return ok(message="invite sent", auth_url=auth_url, **result)


@bp.post("/users/refresh-token")
def refresh_user_token():
    oauth_service = current_app.extensions["oauth_service"]
    payload = request.get_json(silent=True) or {}
    user_key = str(payload.get("user_key") or request.form.get("user_key") or "").strip()
    if not user_key:
        return err("user_key is required", 400)

    try:
        session_record = oauth_service.refresh_access_token(user_key)
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 500)

    tokens = session_record["tokens"]
    return ok(
        message="token refreshed",
        user_key=session_record["user_key"],
        user_name=session_record.get("user_info", {}).get("name"),
        token_scope=tokens.get("scope"),
        access_token_expires_at=tokens.get("access_token_expires_at"),
        refresh_token_expires_at=tokens.get("refresh_token_expires_at"),
        saved_at=tokens.get("saved_at"),
    )


@bp.post("/users/refresh-tokens")
def refresh_all_user_tokens():
    oauth_service = current_app.extensions["oauth_service"]

    result = oauth_service.refresh_all_access_tokens()
    return ok(message="all user tokens refreshed", **result)
