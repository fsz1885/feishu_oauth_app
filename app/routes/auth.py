from __future__ import annotations

from hmac import compare_digest
from html import escape as html_escape

from flask import Blueprint, current_app, redirect, request, session, url_for

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

    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>登录</title>
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
          width: min(360px, calc(100vw - 32px));
          background: white;
          border: 1px solid #dbe3ef;
          border-radius: 12px;
          padding: 24px;
          box-shadow: 0 8px 24px rgba(31, 41, 55, 0.06);
        }}
        h1 {{ margin: 0 0 18px; font-size: 24px; }}
        label {{ display: block; font-weight: 700; margin-bottom: 8px; }}
        input, button {{
          width: 100%;
          box-sizing: border-box;
          font: inherit;
          padding: 11px 12px;
          border-radius: 10px;
        }}
        input {{ border: 1px solid #dbe3ef; margin-bottom: 14px; }}
        button {{
          border: 0;
          background: #2563eb;
          color: white;
          cursor: pointer;
          font-weight: 700;
        }}
        .error {{
          margin-bottom: 12px;
          color: #b91c1c;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 10px;
          padding: 10px 12px;
        }}
      </style>
    </head>
    <body>
      <form class="panel" method="post" action="{url_for("auth.frontend_login")}">
        <h1>工具登录</h1>
        {f'<div class="error">{html_escape(error_text)}</div>' if error_text else ''}
        <input type="hidden" name="next" value="{html_escape(next_url)}" />
        <label for="username">用户名</label>
        <input id="username" name="username" type="text" autocomplete="username" autofocus required />
        <label for="password">密码</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">登录</button>
      </form>
    </body>
    </html>
    """


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
        input, select, textarea, button, .button-link {{
          font: inherit;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 10px;
          box-sizing: border-box;
        }}
        textarea {{ min-height: 110px; resize: vertical; }}
        button, .button-link {{
          background: var(--primary);
          color: white;
          border: none;
          cursor: pointer;
        }}
        .button-link {{
          display: inline-block;
          text-decoration: none;
        }}
        button.secondary, .button-link.secondary {{
          background: #eef2ff;
          color: #1e3a8a;
          border: 1px solid #c7d2fe;
        }}
        .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .share-grid {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-top: 14px;
        }}
        .member-list {{
          display: grid;
          gap: 8px;
          margin-top: 10px;
        }}
        .member-item {{
          display: flex;
          justify-content: space-between;
          gap: 10px;
          align-items: center;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 10px;
          background: #f8fafc;
        }}
        .member-main {{ font-weight: 700; }}
        .member-sub {{ color: var(--muted); font-size: 12px; margin-top: 3px; }}
        .status {{
          margin-top: 10px;
          padding: 10px 12px;
          border-radius: 10px;
          border: 1px solid var(--border);
          background: #f8fafc;
          color: var(--muted);
        }}
        .status:empty {{ display: none; }}
        .status.info {{ background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }}
        .status.success {{ background: #ecfdf5; color: #047857; border-color: #a7f3d0; }}
        .status.error {{ background: #fef2f2; color: #b91c1c; border-color: #fecaca; }}
        .copy-box {{
          width: 100%;
          min-height: 82px;
          background: #f8fafc;
        }}
        pre, .result-box {{
          white-space: pre-wrap;
          word-break: break-word;
          background: #0f172a;
          color: #e2e8f0;
          padding: 14px;
          border-radius: 12px;
          overflow: auto;
        }}
        .result-box {{
          display: grid;
          gap: 12px;
        }}
        .result-card {{
          background: #111827;
          border: 1px solid #334155;
          border-radius: 10px;
          padding: 12px;
        }}
        .result-title {{
          color: #f8fafc;
          font-weight: 700;
          margin-bottom: 6px;
        }}
        .result-meta {{
          color: #94a3b8;
          font-size: 12px;
          margin-bottom: 8px;
        }}
        .result-link {{
          color: #93c5fd;
          font-weight: 700;
        }}
        .result-json {{
          margin-top: 4px;
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
        @media (max-width: 720px) {{ .row, .share-grid {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          <h1>Feishu OAuth + Search Demo</h1>
          <p class="muted">搜索必须选择本地已授权用户，前端只会把选中的 <code>user_key</code> 带到后端。</p>
          <div class="actions">
            <a class="button-link" href="/login">新增授权用户</a>
            <button type="button" class="secondary" id="refreshUsersBtn">刷新用户列表</button>
            <button type="button" class="secondary" id="refreshAllTokensBtn">刷新全部 token</button>
            <a class="button-link secondary" href="/users" target="_blank" rel="noopener noreferrer">查看 /users</a>
          </div>
          <div class="share-grid">
            <div class="field">
              <label for="inviteUrl">发送给别人的授权链接</label>
              <textarea id="inviteUrl" class="copy-box" readonly>{html_escape(invite_url)}</textarea>
              <div class="actions">
                <button type="button" class="secondary" data-copy-target="inviteUrl">复制授权链接</button>
                <a class="button-link secondary" href="/invite" target="_blank" rel="noopener noreferrer">预览邀请页</a>
              </div>
            </div>
            <div class="field">
              <label for="inviteText">可直接发送的邀请文案</label>
              <textarea id="inviteText" class="copy-box" readonly>{html_escape(invite_text)}</textarea>
              <div class="actions">
                <button type="button" class="secondary" data-copy-target="inviteText">复制邀请文案</button>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>搜索通讯录并发送授权邀请</h2>
          <div class="row">
            <div>
              <div class="field">
                <label for="inviteKeyword">用户名关键词</label>
                <input id="inviteKeyword" type="text" placeholder="输入姓名、英文名、邮箱或手机号" />
              </div>
              <div class="actions">
                <button type="button" id="searchInviteUsersBtn">搜索通讯录成员</button>
                <button type="button" class="secondary" id="refreshContactsBtn">刷新通讯录缓存</button>
              </div>
            </div>
            <div>
              <div class="field">
                <label for="inviteUserSelect">匹配成员</label>
                <select id="inviteUserSelect">
                  <option value="">请先搜索通讯录成员</option>
                </select>
              </div>
              <div class="field">
                <label for="inviteMessage">邀请消息</label>
                <textarea id="inviteMessage" placeholder="留空则使用默认授权邀请文案"></textarea>
              </div>
              <div class="actions">
                <button type="button" id="sendInviteBtn">发送授权邀请</button>
                <button type="button" class="secondary" id="addCaptureTargetBtn">加入抓取用户组</button>
              </div>
              <div class="tiny muted">邀请只用于让对方点击授权；文档搜索仍然只能选择本地已授权用户的 user_key。</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>指定用户内容抓取</h2>
          <div class="row">
            <div>
              <div class="actions">
                <button type="button" id="runCaptureBtn">立即抓取新增文字记录</button>
                <button type="button" class="secondary" id="refreshCaptureTargetsBtn">刷新抓取用户组</button>
              </div>
              <div class="tiny muted">每日后台会自动搜索用户组内成员新增的“文字记录”文件；需要配置 CAPTURE_TARGET_FOLDER_TOKEN 才会执行复制。</div>
            </div>
            <div>
              <div class="member-list" id="captureTargetList"></div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>搜索面板</h2>
          <div class="row">
            <div>
              <div class="field">
                <label for="keyword">搜索关键词 q</label>
                <input id="keyword" type="text" placeholder="例如：项目、文字记录" value="" />
              </div>
              <div class="field">
                <label for="userSelect">选择已授权用户</label>
                <input id="userFilter" type="text" placeholder="输入用户名、open_id 或 user_id 过滤" />
                <select id="userSelect">
                  <option value="">请选择一个已授权用户</option>
                </select>
                <div class="tiny muted">当前匹配用户数：<span id="userCount">{len(users)}</span></div>
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
                  {''.join(f'<span class="pill">{html_escape(s)}</span>' for s in scope_text.split())}
                </div>
              </div>
              <div class="field">
                <label>调试授权链接</label>
                <textarea readonly>{html_escape(auth_url)}</textarea>
              </div>
              <div class="tiny muted">首次使用请先点“新增授权用户”，授权成功后再回来搜索。</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>复制文档到文件夹</h2>
          <div class="row">
            <div>
              <div class="field">
                <label for="sourceDocumentId">源文档</label>
                <input id="sourceDocumentId" type="text" placeholder="粘贴 docx 链接或输入 document_id" />
              </div>
              <div class="field">
                <label for="cloneTitle">新文档标题</label>
                <input id="cloneTitle" type="text" placeholder="留空则使用 Copied document" />
              </div>
            </div>
            <div>
              <div class="field">
                <label for="cloneFolderToken">目标 folder token</label>
                <input id="cloneFolderToken" type="text" placeholder="输入目标文件夹 token" />
              </div>
              <div class="actions">
                <button type="button" id="cloneDocBtn">读取并复制到文件夹</button>
              </div>
              <div class="tiny muted">当前版本会复制源 docx 的纯文本内容，不复制图片、表格样式或复杂块结构。</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>搜索结果</h2>
          <div id="resultBox" class="result-box">点击“开始搜索”后，这里会显示 JSON 结果。</div>
        </div>
      </div>

      <script>
        let allAuthorizedUsers = [];
        let inviteSearchResults = [];

        async function fetchUsers() {{
          const res = await fetch('/users');
          const data = await res.json();
          if (!data.ok) {{
            throw new Error(data.error || '加载用户失败');
          }}
          return data.users || [];
        }}

        function userMatchesFilter(user, filterText) {{
          if (!filterText) {{
            return true;
          }}
          const haystack = [
            user.name,
            user.user_key,
            user.open_id,
            user.user_id,
          ].filter(Boolean).join(' ').toLowerCase();
          return haystack.includes(filterText.toLowerCase());
        }}

        function renderUserOptions(users) {{
          const select = document.getElementById('userSelect');
          const countEl = document.getElementById('userCount');
          const previousValue = select.value;
          const filterText = document.getElementById('userFilter').value.trim();
          const visibleUsers = users.filter((u) => userMatchesFilter(u, filterText));
          select.innerHTML = '<option value="">请选择一个已授权用户</option>';
          visibleUsers.forEach((u) => {{
            const opt = document.createElement('option');
            opt.value = u.user_key || '';
            const displayName = u.name || '未命名用户';
            const suffix = u.open_id ? ` | ${{u.open_id}}` : (u.user_id ? ` | ${{u.user_id}}` : '');
            opt.textContent = `${{displayName}}${{suffix}}`;
            select.appendChild(opt);
          }});
          if (visibleUsers.some((u) => u.user_key === previousValue)) {{
            select.value = previousValue;
          }}
          countEl.textContent = String(visibleUsers.length);
        }}

        async function loadUsers() {{
          const box = document.getElementById('resultBox');
          try {{
            const users = await fetchUsers();
            allAuthorizedUsers = users;
            renderUserOptions(allAuthorizedUsers);
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
            if (data.ok) {{
              renderSearchResults(data);
            }} else {{
              box.textContent = JSON.stringify(data, null, 2);
            }}
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

        async function refreshAllUserTokens() {{
          const box = document.getElementById('resultBox');
          box.textContent = '正在刷新全部用户 token...';
          try {{
            const res = await fetch('/users/refresh-tokens', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
            }});
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
            if (data.ok) {{
              await loadUsers();
            }}
          }} catch (err) {{
            box.textContent = '刷新全部 token 失败：' + err.message;
          }}
        }}

        function renderInviteUsers(users) {{
          const select = document.getElementById('inviteUserSelect');
          select.innerHTML = '<option value="">请选择一个匹配成员</option>';
          users.forEach((u, index) => {{
            const opt = document.createElement('option');
            opt.value = String(index);
            const displayName = u.name || u.en_name || '未命名成员';
            const idText = u.open_id || u.user_id || u.email || '';
            opt.textContent = `${{displayName}}${{idText ? ' | ' + idText : ''}}`;
            select.appendChild(opt);
          }});
        }}

        function getFileToken(file) {{
          return file.token || file.docs_token || file.doc_token || file.obj_token || file.document_id || file.file_token || '';
        }}

        function getFileTitle(file, index) {{
          return file.title || file.name || file.docs_name || file.file_name || `搜索结果 ${{index + 1}}`;
        }}

        function getFileUrl(file) {{
          const token = getFileToken(file);
          return file.url || (token ? `https://gemdalesh.feishu.cn/docx/${{token}}` : '');
        }}

        function renderSearchResults(data) {{
          const box = document.getElementById('resultBox');
          box.innerHTML = '';

          const header = document.createElement('div');
          header.textContent = `找到 ${{data.count || 0}} 条结果`;
          box.appendChild(header);

          const files = data.files || [];
          if (!files.length) {{
            const empty = document.createElement('div');
            empty.className = 'muted';
            empty.textContent = '没有搜索到结果。';
            box.appendChild(empty);
          }}

          files.forEach((file, index) => {{
            const card = document.createElement('div');
            card.className = 'result-card';

            const title = document.createElement('div');
            title.className = 'result-title';
            title.textContent = getFileTitle(file, index);
            card.appendChild(title);

            const token = getFileToken(file);
            const meta = document.createElement('div');
            meta.className = 'result-meta';
            meta.textContent = token ? `token: ${{token}}` : '未返回 token，无法构建链接';
            card.appendChild(meta);

            const url = getFileUrl(file);
            if (url) {{
              const link = document.createElement('a');
              link.className = 'result-link';
              link.href = url;
              link.target = '_blank';
              link.rel = 'noopener noreferrer';
              link.textContent = url;
              card.appendChild(link);
            }}

            box.appendChild(card);
          }});

          const details = document.createElement('details');
          const summary = document.createElement('summary');
          summary.textContent = '查看完整 JSON';
          details.appendChild(summary);

          const json = document.createElement('pre');
          json.className = 'result-json';
          json.textContent = JSON.stringify(data, null, 2);
          details.appendChild(json);
          box.appendChild(details);
        }}

        async function loadInviteContacts() {{
          const box = document.getElementById('resultBox');
          try {{
            const res = await fetch('/invite/contacts?limit=500');
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '加载通讯录缓存失败');
            }}
            inviteSearchResults = data.users || [];
            renderInviteUsers(inviteSearchResults);
          }} catch (err) {{
            box.textContent = '加载通讯录缓存失败：' + err.message;
          }}
        }}

        async function refreshInviteContacts() {{
          const box = document.getElementById('resultBox');
          box.textContent = '正在刷新通讯录缓存...';
          try {{
            const res = await fetch('/invite/contacts/refresh', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
            }});
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '刷新通讯录缓存失败');
            }}
            inviteSearchResults = data.users || [];
            renderInviteUsers(inviteSearchResults);
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '刷新通讯录缓存失败：' + err.message;
          }}
        }}

        async function searchInviteUsers() {{
          const keyword = document.getElementById('inviteKeyword').value.trim();
          const box = document.getElementById('resultBox');
          if (!keyword) {{
            box.textContent = '请先输入用户名关键词。';
            return;
          }}

          box.textContent = '正在搜索通讯录成员...';
          try {{
            const res = await fetch('/invite/search-users', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ q: keyword }}),
            }});
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '搜索通讯录失败');
            }}
            inviteSearchResults = data.users || [];
            renderInviteUsers(inviteSearchResults);
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '搜索通讯录失败：' + err.message;
          }}
        }}

        async function sendInvite() {{
          const selectedIndex = document.getElementById('inviteUserSelect').value;
          const message = document.getElementById('inviteMessage').value.trim();
          const box = document.getElementById('resultBox');
          const selectedUser = inviteSearchResults[Number(selectedIndex)];

          if (!selectedUser) {{
            box.textContent = '请先搜索并选择一个通讯录成员。';
            return;
          }}

          const receiveId = selectedUser.open_id || selectedUser.user_id;
          const receiveIdType = selectedUser.open_id ? 'open_id' : 'user_id';
          if (!receiveId) {{
            box.textContent = '所选成员没有可用于发送邀请的 open_id 或 user_id。';
            return;
          }}

          box.textContent = '正在发送授权邀请...';
          try {{
            const res = await fetch('/invite/send', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{
                open_id: selectedUser.open_id || '',
                name: selectedUser.name || selectedUser.en_name || '',
                receive_id: receiveId,
                receive_id_type: receiveIdType,
                message,
              }}),
            }});
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '发送授权邀请失败：' + err.message;
          }}
        }}

        function renderCaptureTargets(targets) {{
          const list = document.getElementById('captureTargetList');
          list.innerHTML = '';
          if (!targets.length) {{
            const empty = document.createElement('div');
            empty.className = 'tiny muted';
            empty.textContent = '还没有指定抓取用户，请先在通讯录里搜索并加入。';
            list.appendChild(empty);
            return;
          }}

          targets.forEach((target) => {{
            const item = document.createElement('div');
            item.className = 'member-item';

            const main = document.createElement('div');
            const name = document.createElement('div');
            name.className = 'member-main';
            name.textContent = target.name || target.en_name || '未命名用户';
            const sub = document.createElement('div');
            sub.className = 'member-sub';
            sub.textContent = target.open_id || target.user_id || target.target_key || '';
            main.appendChild(name);
            main.appendChild(sub);

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'secondary';
            removeBtn.textContent = '移除';
            removeBtn.addEventListener('click', () => removeCaptureTarget(target.target_key));

            item.appendChild(main);
            item.appendChild(removeBtn);
            list.appendChild(item);
          }});
        }}

        async function loadCaptureTargets() {{
          const box = document.getElementById('resultBox');
          try {{
            const res = await fetch('/capture/targets');
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '加载抓取用户组失败');
            }}
            renderCaptureTargets(data.targets || []);
          }} catch (err) {{
            box.textContent = '加载抓取用户组失败：' + err.message;
          }}
        }}

        async function addCaptureTargetFromSelectedInviteUser() {{
          const selectedIndex = document.getElementById('inviteUserSelect').value;
          const box = document.getElementById('resultBox');
          const selectedUser = inviteSearchResults[Number(selectedIndex)];
          if (!selectedUser) {{
            box.textContent = '请先在通讯录里搜索并选择一个成员。';
            return;
          }}

          try {{
            const res = await fetch('/capture/targets', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ user: selectedUser }}),
            }});
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '加入抓取用户组失败');
            }}
            box.textContent = JSON.stringify(data, null, 2);
            await loadCaptureTargets();
          }} catch (err) {{
            box.textContent = '加入抓取用户组失败：' + err.message;
          }}
        }}

        async function removeCaptureTarget(targetKey) {{
          const box = document.getElementById('resultBox');
          try {{
            const res = await fetch('/capture/targets/' + encodeURIComponent(targetKey), {{
              method: 'DELETE',
            }});
            const data = await res.json();
            if (!data.ok) {{
              throw new Error(data.error || '移除抓取用户失败');
            }}
            box.textContent = JSON.stringify(data, null, 2);
            await loadCaptureTargets();
          }} catch (err) {{
            box.textContent = '移除抓取用户失败：' + err.message;
          }}
        }}

        async function runCaptureNow() {{
          const box = document.getElementById('resultBox');
          box.textContent = '正在抓取新增文字记录...';
          try {{
            const res = await fetch('/capture/run', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
            }});
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '抓取失败：' + err.message;
          }}
        }}

        async function cloneDocumentToFolder() {{
          const userKey = document.getElementById('userSelect').value.trim();
          const sourceDocumentId = document.getElementById('sourceDocumentId').value.trim();
          const targetFolderToken = document.getElementById('cloneFolderToken').value.trim();
          const title = document.getElementById('cloneTitle').value.trim();
          const box = document.getElementById('resultBox');

          if (!userKey) {{
            box.textContent = '请先选择一个已授权用户。';
            return;
          }}
          if (!sourceDocumentId) {{
            box.textContent = '请先输入源文档 document_id。';
            return;
          }}
          if (!targetFolderToken) {{
            box.textContent = '请先输入目标 folder token。';
            return;
          }}

          box.textContent = '正在读取源文档并创建新文档...';
          try {{
            const res = await fetch('/docx/clone-plain-text', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{
                user_key: userKey,
                source_document_id: sourceDocumentId,
                target_folder_token: targetFolderToken,
                title,
              }}),
            }});
            const data = await res.json();
            box.textContent = JSON.stringify(data, null, 2);
          }} catch (err) {{
            box.textContent = '复制文档失败：' + err.message;
          }}
        }}

        async function autoFillCloneTitle() {{
          const userKey = document.getElementById('userSelect').value.trim();
          const sourceDocumentId = document.getElementById('sourceDocumentId').value.trim();
          const titleInput = document.getElementById('cloneTitle');

          if (!userKey || !sourceDocumentId) {{
            return;
          }}

          // 如果用户已经手动输入了标题，不要覆盖
          if (titleInput.value.trim()) {{
            return;
          }}

          try {{
            const params = new URLSearchParams();
            params.set('user_key', userKey);
            params.set('source_document_id', sourceDocumentId);
            const res = await fetch('/docx/minutes-meta?' + params.toString());
            const data = await res.json();
            if (data.ok && data.meta && data.meta.suggested_filename) {{
              titleInput.value = data.meta.suggested_filename;
            }}
          }} catch (err) {{
            // 静默失败，不打扰用户
            console.error('获取建议标题失败:', err);
          }}
        }}

        document.getElementById('sourceDocumentId').addEventListener('blur', autoFillCloneTitle);
        document.getElementById('userSelect').addEventListener('change', autoFillCloneTitle);

        document.getElementById('refreshUsersBtn').addEventListener('click', loadUsers);
        document.getElementById('searchInviteUsersBtn').addEventListener('click', searchInviteUsers);
        document.getElementById('refreshContactsBtn').addEventListener('click', refreshInviteContacts);
        document.getElementById('sendInviteBtn').addEventListener('click', sendInvite);
        document.getElementById('addCaptureTargetBtn').addEventListener('click', addCaptureTargetFromSelectedInviteUser);
        document.getElementById('runCaptureBtn').addEventListener('click', runCaptureNow);
        document.getElementById('refreshCaptureTargetsBtn').addEventListener('click', loadCaptureTargets);
        document.getElementById('searchBtn').addEventListener('click', doSearch);
        document.getElementById('refreshTokenBtn').addEventListener('click', refreshSelectedUserToken);
        document.getElementById('refreshAllTokensBtn').addEventListener('click', refreshAllUserTokens);
        document.getElementById('cloneDocBtn').addEventListener('click', cloneDocumentToFolder);
        document.getElementById('fillExampleBtn').addEventListener('click', () => {{
          document.getElementById('keyword').value = '文字记录';
          document.getElementById('docsTypes').value = 'doc';
        }});
        document.querySelectorAll('[data-copy-target]').forEach((btn) => {{
          btn.addEventListener('click', async () => {{
            const target = document.getElementById(btn.dataset.copyTarget);
            if (!target) return;
            const oldText = btn.textContent;
            const markCopied = () => {{
              btn.textContent = '已复制';
              setTimeout(() => {{ btn.textContent = oldText; }}, 1200);
            }};
            try {{
              if (!navigator.clipboard) {{
                throw new Error('Clipboard API unavailable');
              }}
              await navigator.clipboard.writeText(target.value);
              markCopied();
            }} catch (err) {{
              target.focus();
              target.select();
              if (document.execCommand('copy')) {{
                markCopied();
              }} else {{
                btn.textContent = '复制失败';
                setTimeout(() => {{ btn.textContent = oldText; }}, 1600);
              }}
            }}
          }});
        }});

        loadUsers();
        loadInviteContacts();
        loadCaptureTargets();
      </script>
    </body>
    </html>
    """


@bp.get("/invite")
def invite():
    return """
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>飞书授权邀请</title>
      <style>
        body { margin: 0; font-family: Arial, Helvetica, sans-serif; background: #f6f8fb; color: #111827; }
        .wrap { max-width: 680px; margin: 56px auto; padding: 0 18px; }
        .panel { background: white; border: 1px solid #dbe3ef; border-radius: 16px; padding: 28px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.06); }
        h1 { margin-top: 0; font-size: 30px; }
        p { color: #4b5563; line-height: 1.7; }
        a.button { display: inline-block; margin-top: 14px; padding: 12px 18px; background: #2563eb; color: white; text-decoration: none; border-radius: 10px; font-weight: 700; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="panel">
          <h1>飞书账号授权</h1>
          <p>请点击下面的按钮完成飞书授权。授权成功后，发起人就可以在工具里选择你的账号进行云文档搜索。</p>
          <p>授权只会保存你的飞书用户标识和访问凭证，不需要你手动复制任何 code 或 token。</p>
          <a class="button" href="/login">开始授权</a>
        </div>
      </div>
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
