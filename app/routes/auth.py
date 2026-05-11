from __future__ import annotations

from html import escape as html_escape

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
        @media (max-width: 720px) {{ .row, .share-grid {{ grid-template-columns: 1fr; }} }}
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
          <div class="share-grid">
            <div class="field">
              <label for="inviteUrl">发送给别人的授权链接</label>
              <textarea id="inviteUrl" class="copy-box" readonly>{html_escape(invite_url)}</textarea>
              <div class="actions">
                <button type="button" class="secondary" data-copy-target="inviteUrl">复制授权链接</button>
                <a href="/invite" target="_blank"><button type="button" class="secondary">预览邀请页</button></a>
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
              </div>
              <div class="tiny muted">邀请只用于让对方点击授权；文档搜索仍然只能选择本地已授权用户的 user_key。</div>
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
          <pre id="resultBox">点击“开始搜索”后，这里会显示 JSON 结果。</pre>
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

        document.getElementById('refreshUsersBtn').addEventListener('click', loadUsers);
        document.getElementById('searchInviteUsersBtn').addEventListener('click', searchInviteUsers);
        document.getElementById('refreshContactsBtn').addEventListener('click', refreshInviteContacts);
        document.getElementById('sendInviteBtn').addEventListener('click', sendInvite);
        document.getElementById('searchBtn').addEventListener('click', doSearch);
        document.getElementById('refreshTokenBtn').addEventListener('click', refreshSelectedUserToken);
        document.getElementById('cloneDocBtn').addEventListener('click', cloneDocumentToFolder);
        document.getElementById('fillExampleBtn').addEventListener('click', () => {{
          document.getElementById('keyword').value = '文字记录';
          document.getElementById('docsTypes').value = 'doc';
        }});
        document.querySelectorAll('[data-copy-target]').forEach((btn) => {{
          btn.addEventListener('click', async () => {{
            const target = document.getElementById(btn.dataset.copyTarget);
            if (!target) return;
            try {{
              await navigator.clipboard.writeText(target.value);
              const oldText = btn.textContent;
              btn.textContent = '已复制';
              setTimeout(() => {{ btn.textContent = oldText; }}, 1200);
            }} catch (err) {{
              target.focus();
              target.select();
              document.execCommand('copy');
            }}
          }});
        }});

        loadUsers();
        loadInviteContacts();
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
