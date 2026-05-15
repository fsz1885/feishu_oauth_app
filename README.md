# Feishu OAuth + Cloud Docs Search

一个适合本地开发和后续扩展的飞书 OAuth 小工程，已支持：

- 浏览器授权登录
- 显式申请 `offline_access`
- 本地持久化 `access_token` / `refresh_token` / 用户信息
- 自动检测 `access_token` 是否过期，并在需要时使用 `refresh_token` 刷新
- 使用 `user_access_token` 调用飞书云文档搜索接口
- 工程化目录结构，方便后续扩展更多 Feishu API

## 为什么要这样做

飞书的 OAuth 授权码需要先获取 `code`，再换 `user_access_token`；`user_access_token` 有有效期，官方提供刷新接口来获取新的 `user_access_token` 和新的 `refresh_token`。同时，获取授权码时需要在授权页请求所需的 `scope`，返回 token 的实际权限以 `scope` 字段为准。获取用户信息可以通过 `user_access_token` 调用 `authen/v1/user_info` 接口。

## 当前申请的 scope

默认请求以下 scope：

- `auth:user.id:read`
- `offline_access`
- `drive:drive.search:readonly`
- `contact:user.base:readonly`

说明：

- `offline_access` 用于拿到 `refresh_token` 并做续期。
- `drive:drive.search:readonly` 是搜索云文档所需权限。

## 目录结构

```text
feishu_oauth_app/
├── .env.example
├── README.md
├── requirements.txt
├── run.py
├── data/
│   └── auth_store.json          # 运行后自动生成
└── app/
    ├── __init__.py              # Flask app 工厂
    ├── config.py                # 配置与 scope
    ├── routes/
    │   ├── __init__.py
    │   ├── auth.py              # / /login /callback /users
    │   └── search.py            # /search
    ├── services/
    │   ├── feishu_oauth.py      # 授权、换 token、刷新 token、获取用户信息
    │   └── feishu_search.py     # 云文档搜索
    ├── storage/
    │   └── json_store.py        # 本地 JSON 持久化
    └── utils/
        ├── response.py          # 统一响应
        └── time_utils.py        # 过期时间处理
```

## 启动方式 

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

把 `.env.example` 复制成 `.env`，填入你自己的飞书应用配置。

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后修改：

```env
FEISHU_APP_ID=你的_APP_ID
FEISHU_APP_SECRET=你的_APP_SECRET
FEISHU_REDIRECT_URI=http://localhost:8080/callback
```

> `FEISHU_REDIRECT_URI` 必须和飞书开发者后台里配置的重定向 URL 完全一致。授权完成后，飞书会把浏览器跳回这个地址，并附带 `code`。

### 3. 启动程序

```bash
python run.py
```

默认地址：

```text
http://localhost:8080/
```

首页现在提供了一个最小可用前端页面，包含：

- 已授权用户下拉框
- 搜索关键词输入框
- docs_types 输入框
- 搜索结果 JSON 展示区域
- 新增授权用户按钮

## 使用流程

### 第一步：授权

打开：

```text
http://localhost:8080/login
```

授权成功后：

- 程序会把 `access_token`、`refresh_token`、用户信息写入本地 JSON 文件
- 响应中会返回 `scope`、`has_offline_access`、`has_drive_search_scope` 等信息

### 第二步：在首页前端下拉框中选择用户并搜索

打开首页：

```text
http://localhost:8080/
```

页面会自动读取本地已授权用户并填充到下拉框中。你可以：

- 先点击“新增授权用户”继续添加新用户
- 在下拉框里选择某个已授权用户
- 点击“刷新当前用户 token”手动刷新该用户的 token
- 输入关键词并点击“开始搜索”

前端下拉框展示的是用户名，但提交给后端的是该用户的 `user_key`，这样比按 `name` 传参更稳定。

### 第三步：查看本地已保存用户

```text
http://localhost:8080/users
```

### 第四步：通过接口直接搜索云文档

搜索接口必须显式传入 `user_key`（例如 open_id），不会再默认使用最近一次授权成功的用户，也不会用 `name` 查找用户：

```text
http://localhost:8080/search?q=项目&user_key=ou_xxx
```

指定文档类型：

```text
http://localhost:8080/search?q=项目&user_key=ou_xxx&docs_types=doc,sheet
```

如果本地保存的 `access_token` 已过期，程序会自动尝试用 `refresh_token` 刷新；如果 `refresh_token` 也过期了，则会提示重新授权。飞书刷新 token 后需要更新本地保存的 `user_access_token` 和 `refresh_token`，不要继续使用旧值。

也可以手动刷新指定用户的 token：

```bash
curl -X POST http://localhost:8080/users/refresh-token \
  -H "Content-Type: application/json" \
  -d "{\"user_key\":\"ou_xxx\"}"
```

## 本地存储格式

程序默认把认证信息保存到：

```text
data/auth_store.json
```

结构大致如下：

```json
{
  "latest_user_key": "ou_xxx",
  "users": {
    "ou_xxx": {
      "user_info": {
        "open_id": "ou_xxx",
        "name": "Alice"
      },
      "tokens": {
        "access_token": "...",
        "expires_in": 7200,
        "access_token_expires_at": "2026-04-27T02:00:00+00:00",
        "refresh_token": "...",
        "refresh_token_expires_in": 604800,
        "refresh_token_expires_at": "2026-05-04T02:00:00+00:00",
        "token_type": "Bearer",
        "scope": "...",
        "saved_at": "2026-04-27T00:00:00+00:00"
      }
    }
  }
}
```

## 后续扩展建议

你后面可以直接在这个结构上加：

- Feishu 文档读取
- 多维表格读写
- Slides / Docs / Sheets 操作
- 前端用户下拉框选择与切换
- 多用户选择与切换
- SQLite / MySQL / Redis 持久化
- 登录态 cookie / session / 前端页面

推荐扩展方式：

- 新接口能力放到 `app/services/` 里
- 新路由放到 `app/routes/` 里
- 本地文件存储替换数据库时，只需要替换 `app/storage/` 层

## 安全提醒

- 不要把 `APP_SECRET` 提交到 Git
- 不要把真实 token 文件提交到 Git
- 正式环境建议加密存储 token，或改用数据库 / 密钥管理服务
- 本项目当前更适合本地开发和内网工具，不建议直接裸奔到公网

## 搜索接口现在是怎么运行的

`/search` 的执行流程如下：

1. 读取查询参数：
   - `q`：搜索关键词，必填
   - `user_key`：必填，通常是 open_id
   - `docs_types`：可选，文档类型过滤，例如 `doc,sheet`

2. 选择使用哪个本地授权用户：
   - 只按 `user_key` 取用户
   - 如果没传 `user_key`，或者传了旧的 `name` 参数，会直接返回错误

3. 检查 token 是否可用：
   - 如果 `access_token` 还没过期，直接使用
   - 如果已过期但 `refresh_token` 还有效，则自动刷新并回写本地 JSON
   - 如果 `refresh_token` 也过期，就提示重新 `/login` 授权

4. 调用飞书搜索接口：
   - 使用该用户的 `user_access_token`
   - 请求体为 `search_key / count / offset / docs_types / owner_ids / chat_ids`
   - 按页拉取，直到 `has_more=false` 或达到本地设置的页数上限

5. 返回结果：
   - 当前实际使用的 `user_key`
   - 当前实际使用的 `user_name`
   - 当前 token 的 scope
   - token 过期时间
   - 文档搜索结果列表

## 手动刷新 token 现在是怎么运行的

`/users/refresh-token` 的执行流程如下：

1. 从 JSON 请求体读取 `user_key`
2. 按 `user_key` 读取本地保存的用户 token
3. 使用该用户的 `refresh_token` 调用飞书刷新接口
4. 把新的 token 信息回写到本地 JSON
5. 返回新的 token 过期时间、scope 和保存时间，不返回真实 token 值

## 前端页面现在是怎么运行的

首页 `/` 会渲染一个内嵌 HTML 页面。页面加载后会自动请求 `/users`，把本地已授权用户填充到下拉框。

当你点击“开始搜索”时，前端会：

1. 读取关键词 `q`
2. 读取下拉框里选中的 `user_key`
3. 读取 `docs_types`
4. 通过 `fetch` 调用 `/search?q=...&user_key=...&docs_types=...`
5. 把后端返回的 JSON 直接显示在页面下方

当你点击“刷新当前用户 token”时，前端会把当前下拉框选中的 `user_key` POST 到 `/users/refresh-token`，然后把刷新结果显示在页面下方。

也就是说：前端只负责“选择用户 + 拼接参数 + 展示结果”，真正的 token 校验、自动刷新、调用飞书搜索接口仍然都在后端完成。
