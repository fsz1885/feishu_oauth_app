from __future__ import annotations

from flask import Blueprint, current_app, redirect, request

from app.utils.response import err, ok

bp = Blueprint("auth", __name__)


@bp.get("/")
def index():
    oauth_service = current_app.extensions["oauth_service"]
    store = current_app.extensions["store"]
    auth_url = oauth_service.build_auth_url()
    users = store.list_users()
    scope_text = current_app.config["REQUESTED_SCOPE_STRING"]

    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Feishu OAuth Local Demo</title>
      <style>
        :root {{
          --bg: #f6f8fb;
          --card: #ffffff;
          --text: #1f2937;
          --muted: #6b7280;
          --primary: #2563eb;
          --border: #dbe3ef;
        }}
        body {{
          margin: 0;
          font-family: Arial, Helvetica, sans-serif;
          background: var(--bg);
          color: var(--text);
        }}
        .wrap {{
          max-width: 980px;
          margin: 32px auto;
          padding: 0 16px;
        }}
        .card {{
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 8px 24px rgba(31, 41, 55, 0.06);
          margin-bottom: 16px;
        }}
        h1, h2 {{ margin-top: 0; }}
        .row {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }}
        .field {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }}
        label {{ font-weight: 600; }}
        input, select, textarea, button {{
          font: inherit;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 10px;
          box-sizing: border-box;
        }}
        textarea {{ min-height: 110px; resize: vertical; }}
        button {{
          background: var(--primary);
          color: white;
          border: none;
          cursor: pointer;
        }}
        button.secondary {{
          background: #eef2ff;
          color: #1e3a8a;
          border: 1px solid #c7d2fe;
        }}
        .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        pre {{
          white-space: pre-wrap;
          word-break: break-word;
          background: #0f172a;
          color: #e2e8f0;
          padding: 14px;
          border-radius: 12px;
          overflow: auto;
        }}
        .muted {{ color: var(--muted); }}
        .tiny {{ font-size: 12px; }}
        .pill {{
          display: inline-block;
          padding: 3px 8px;
          border-radius: 999px;
          background: #eff6ff;
          color: #1d4ed8;
          font-size: 12px;
          margin-right: 6px;
        }}
        @media (max-width: 720px) {{ .row {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          <h1>Feishu OAuth + Search Demo</h1>
          <p class="muted">搜索必须选择本地已授权用户，前端只会把选中的 <code>user_key</code> 带到后端。</p>
          <div class="actions">
            <a href="/login"><button type="button">新增授权用户</button></a>
            <button type="button" class="secondary" id="refreshUsersBtn">刷新用户列表</button>
            <a href="/users" target="_blank"><button type="button" class="secondary">查看 /users</button></a>
          </div>
        </div>

        <div class="card">
          <h2>搜索面板</h2>
          <div class="row">
            <div>
              <div class="field">
                <label for="keyword">搜索关键词 q</label>
                <input id="keyword" type="text" placeholder="例如：项目、文字记录" value="项目" />
              </div>
              <div class="field">
                <label for="userSelect">选择已授权用户</label>
                <select id="userSelect">
                  <option value="">请选择一个已授权用户</option>
                </select>
                <div class="tiny muted">当前本地已保存用户数：<span id="userCount">{len(users)}</span></div>
              </div>
              <div class="field">
                <label for="docsTypes">文档类型 docs_types</label>
                <input id="docsTypes" type="text" placeholder="例如：doc,sheet" />
                <div class="tiny muted">可选：doc / sheet / slides / bitable / mindnote / file</div>
              </div>
              <div class="actions">
                <button type="button" id="searchBtn">开始搜索</button>
                <button type="button" class="secondary" id="refreshTokenBtn">刷新当前用户 token</button>
                <button type="button" class="secondary" id="fillExampleBtn">填入示例</button>
              </div>
            </div>
            <div>
              <div class="field">
                <label>当前请求 scope</label>
                <div>
                  {''.join(f'<span class="pill">{s}</span>' for s in scope_text.split())}
                </div>
              </div>
              <div class="field">
                <label>调试授权链接</label>
                <textarea readonly>{auth_url}</textarea>
              </div>
              <div class="tiny muted">首次使用请先点“新增授权用户”，授权成功后再回来搜索。</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>搜索结果</h2>
          <pre id="resultBox">点击“开始搜索”后，这里会显示 JSON 结果。</pre>
        </div>
      </div>

      <script>
        async function fetchUsers() {{
          const res = await fetch('/users');
          const data = await res.json();
          if (!data.ok) {{
            throw new Error(data.error || '加载用户失败');
          }}
          return data.users || [];
        }}

        function renderUserOptions(users) {{
          const select = document.getElementById('userSelect');
          const countEl = document.getElementById('userCount');
          select.innerHTML = '<option value="">请选择一个已授权用户</option>';
          users.forEach((u) => {{
            const opt = document.createElement('option');
            opt.value = u.user_key || '';
            const displayName = u.name || '未命名用户';
            const suffix = u.open_id ? ` | ${{u.open_id}}` : (u.user_id ? ` | ${{u.user_id}}` : '');
            opt.textContent = `${{displayName}}${{suffix}}`;
            select.appendChild(opt);
          }});
          countEl.textContent = String(users.length);
        }}

        async function loadUsers() {{
          const box = document.getElementById('resultBox');
          try {{
            const users = await fetchUsers();
            renderUserOptions(users);
            if (!users.length) {{
              box.textContent = '当前还没有本地已授权用户，请先点击“新增授权用户”。';
            }}
          }} catch (err) {{
            box.textContent = '加载用户失败：' + err.message;
          }}
        }}

        async function doSearch() {{
          const q = document.getElementById('keyword').value.trim();
          const docsTypes = document.getElementById('docsTypes').value.trim();
          const userKey = document.getElementById('userSelect').value.trim();
          const box = document.getElementById('resultBox');

          if (!q) {{
            box.textContent = '请先输入搜索关键词 q。';
            return;
          }}
          if (!userKey) {{
            box.textContent = '请先选择一个已授权用户，搜索请求必须包含 user_key。';
            return;
          }}

          const params = new URLSearchParams();
          params.set('q', q);
          if (docsTypes) params.set('docs_types', docsTypes);
          params.set('user_key', userKey);

          box.textContent = '搜索中...';
          try {{
            const res = await fetch('/search?' + params.toString());
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '搜索失败：' + err.message;
          }}
        }}

        async function refreshSelectedUserToken() {{
          const userKey = document.getElementById('userSelect').value.trim();
          const box = document.getElementById('resultBox');

          if (!userKey) {{
            box.textContent = '请先选择一个已授权用户，再刷新 token。';
            return;
          }}

          box.textContent = '正在刷新 token...';
          try {{
            const res = await fetch('/users/refresh-token', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ user_key: userKey }}),
            }});
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
            if (data.ok) {{
              await loadUsers();
              document.getElementById('userSelect').value = userKey;
            }}
          }} catch (err) {{
            box.textContent = '刷新 token 失败：' + err.message;
          }}
        }}

        document.getElementById('refreshUsersBtn').addEventListener('click', loadUsers);
        document.getElementById('searchBtn').addEventListener('click', doSearch);
        document.getElementById('refreshTokenBtn').addEventListener('click', refreshSelectedUserToken);
        document.getElementById('fillExampleBtn').addEventListener('click', () => {{
          document.getElementById('keyword').value = '文字记录';
          document.getElementById('docsTypes').value = 'doc';
        }});

        loadUsers();
      </script>
    </body>
    </html>
    """


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
    return ok(
        message="授权成功",
        user_key=user_key,
        expires_in=token_payload.get("expires_in"),
        scope=granted_scope,
        token_type=token_payload.get("token_type"),
        has_offline_access=("offline_access" in granted_scope.split()),
        has_drive_search_scope=("drive:drive.search:readonly" in granted_scope.split()),
        next="/",
        user_info=user_info,
    )


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
    return ok(count=len(summary), users=summary, raw=raw_users)


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
