# Feishu Doc Hub

飞书授权 · 云档搜索 · 录音归档 — 已通过上线前压力测试（7/7）的飞书 OAuth 生产服务，支持：

- 浏览器授权登录（`/login` → 飞书授权页 → `/callback`）
- 显式申请 `offline_access`，本地持久化 `access_token` / `refresh_token` / 用户信息
- 自动检测 `access_token` 是否过期，并在需要时使用 `refresh_token` 刷新（含后台定时批量刷新）
- 使用 `user_access_token` 调用飞书云文档搜索接口
- 读取 docx 文档纯文本内容，并在指定文件夹创建新文档
- 提取会议纪要类文档的元信息（录制时间等），自动生成建议文件名
- 搜索企业通讯录成员并发送 OAuth 授权邀请消息（含通讯录缓存与定时刷新）
- 指定用户"文字记录"内容抓取：定时/手动搜索目标用户新增的录制文字记录，自动复制到指定文件夹并去重
- 前端密码保护（除授权/邀请相关公开端点外，所有页面与接口需先登录）
- Docker / docker-compose / `deploy.sh` 一键部署
- 工程化目录结构，方便后续扩展更多 Feishu API

## 为什么要这样做

飞书的 OAuth 授权码需要先获取 `code`，再换 `user_access_token`；`user_access_token` 有有效期，官方提供刷新接口来获取新的 `user_access_token` 和新的 `refresh_token`。同时，获取授权码时需要在授权页请求所需的 `scope`，返回 token 的实际权限以 `scope` 字段为准。获取用户信息可以通过 `user_access_token` 调用 `authen/v1/user_info` 接口。

## 当前申请的 scope

默认请求以下 scope：

- `auth:user.id:read`
- `offline_access`
- `drive:drive.search:readonly`
- `docx:document:readonly`
- `docx:document:create`
- `docx:document:write_only`
- `contact:user.base:readonly`

说明：

- `offline_access` 用于拿到 `refresh_token` 并做续期。
- `drive:drive.search:readonly` 是搜索云文档所需权限。
- `docx:document:*` 是读取、创建和写入 docx 文档所需权限。
- `contact:user.base:readonly` 是获取基础用户信息所需权限。

## 目录结构

```text
feishu_oauth_app/
├── .env.example               # 环境变量模板
├── .dockerignore
├── .gitignore
├── README.md
├── DEPLOY_UBUNTU.md           # Ubuntu + Docker 部署详细教程
├── 一键部署.md                 # Docker 一键部署速查
├── Dockerfile
├── docker-compose.yml
├── deploy.sh                  # 一键部署脚本（up/logs/ps/restart/down/update）
├── requirements.txt
├── run.py
├── data/
│   ├── auth_store.json        # 授权用户与 token，运行后自动生成
│   └── capture_store.json     # 抓取用户组与运行记录，运行后自动生成
└── app/
    ├── __init__.py            # Flask app 工厂，装配 service 并启动后台线程
    ├── config.py              # 配置与 scope
    ├── routes/
    │   ├── __init__.py
    │   ├── auth.py            # / /login /callback /users /invite/* /front-login
    │   ├── capture.py         # /capture/targets /capture/run /capture/runs
    │   ├── docx.py            # /docx/clone-plain-text /docx/minutes-meta
    │   └── search.py          # /search
    ├── services/
    │   ├── feishu_oauth.py    # 授权、换 token、刷新 token、获取用户信息
    │   ├── feishu_search.py   # 云文档搜索
    │   ├── feishu_docx.py     # docx 文档读取、创建与纯文本写入
    │   ├── feishu_invite.py   # 通讯录搜索、缓存与邀请消息
    │   └── content_capture.py # “文字记录”抓取编排与后台调度
    ├── storage/
    │   ├── json_store.py      # 授权信息本地 JSON 持久化
    │   └── capture_store.py   # 抓取目标 / 已处理文件 / 运行记录持久化
    └── utils/
        ├── response.py        # 统一响应
        └── time_utils.py      # 过期时间处理
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
FRONTEND_USERNAME=你的前端登录用户名
FRONTEND_PASSWORD=你的前端访问密码
```

> `FEISHU_REDIRECT_URI` 必须和飞书开发者后台里配置的重定向 URL 完全一致。授权完成后，飞书会把浏览器跳回这个地址，并附带 `code`。

可选环境变量：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `APP_HOST` | `0.0.0.0` | 服务监听地址 |
| `APP_PORT` | `8080` | 服务监听端口 |
| `APP_DEBUG` | `false` | 是否开启 Flask debug 模式 |
| `LOCAL_STORE_PATH` | `data/auth_store.json` | 本地认证信息存储路径 |
| `PUBLIC_BASE_URL` | `""` | 对外暴露的 base URL，用于生成邀请链接（如 `https://your-domain.com`） |
| `FRONTEND_USERNAME` | `admin` | 前端页面与受保护接口的登录用户名 |
| `FRONTEND_PASSWORD` | `change_me_to_a_strong_password` | 前端页面与受保护接口的访问密码，**部署前务必修改** |
| `SESSION_SECRET_KEY` | 取 `FEISHU_APP_SECRET` | Flask session 加密密钥，建议设置为独立的长随机字符串 |
| `CONTACT_CACHE_REFRESH_SECONDS` | `3600` | 通讯录缓存自动刷新间隔（秒） |
| `CONTACT_CACHE_STARTUP_REFRESH` | `true` | 启动时是否立即刷新通讯录缓存 |
| `TOKEN_REFRESH_SECONDS` | `3600` | 后台批量刷新所有用户 token 的间隔（秒） |
| `TOKEN_REFRESH_STARTUP_REFRESH` | `false` | 启动时是否立即批量刷新 token |
| `CAPTURE_STORE_PATH` | `data/capture_store.json` | 抓取用户组与运行记录存储路径 |
| `CAPTURE_REFRESH_SECONDS` | `3600` | 后台自动抓取的间隔（秒，最小 60） |
| `CAPTURE_TARGET_INTERVAL_SECONDS` | `1.0` | 同一轮内相邻抓取目标之间的间隔（秒），用于降低飞书 API 限流风险，`0` 表示不加间隔 |
| `CAPTURE_STARTUP_REFRESH` | `false` | 启动时是否立即执行一次抓取 |
| `CAPTURE_SEARCH_KEYWORD` | `文字记录` | 抓取时搜索文档的关键词 |
| `CAPTURE_TARGET_FOLDER_TOKEN` | `""` | 抓取结果要复制到的目标文件夹 token（为空则运行抓取会报错）；也可在页面底部“高级设置”中在线修改，前端设置优先于环境变量 |

### 3. 启动程序

```bash
python run.py
```

默认地址：

```text
http://localhost:8080/
```

> 首次访问任意受保护页面会先跳转到 `/front-login` 输入 `FRONTEND_USERNAME` 和 `FRONTEND_PASSWORD` 登录；`/login`、`/callback`、`/invite` 保持公开，方便直接分享给同事授权。

---

## Docker 部署

项目已包含 `Dockerfile`、`docker-compose.yml` 和一键脚本 `deploy.sh`，支持容器化部署。

### HTTPS 部署（Caddy + Let's Encrypt，推荐）

生产环境通过 Caddy 反向代理提供 HTTPS（自动申请/续期 Let's Encrypt 免费证书）：

1. 域名 A 记录指向服务器公网 IP，云安全组放行 **80/443**
2. 配置文件在 `deploy/caddy/Caddyfile`（将 `mkt.gemdalesh.cn` 换成你的域名）
3. 启动 Caddy（host 网络，证书数据持久化）：

```bash
mkdir -p /opt/caddy-data /opt/caddy-config
docker run -d --name feishu-caddy --network host --restart unless-stopped \
  -v $PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v /opt/caddy-data:/data -v /opt/caddy-config:/config \
  caddy:2-alpine
```

4. 应用 `.env` 同步改为域名地址：`FEISHU_REDIRECT_URI=https://你的域名/callback`、`PUBLIC_BASE_URL=https://你的域名`，重建应用容器
5. 飞书开发者后台「安全设置」中新增重定向 URL：`https://你的域名/callback`

### 1. 准备环境变量

与本地启动一样，先准备 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env，填入 FEISHU_APP_ID、FEISHU_APP_SECRET 等配置
```

### 2. 使用一键脚本启动（推荐）

```bash
./deploy.sh
```

脚本会自动检测 `docker compose`、从 `.env.example` 生成 `.env`（如缺失）、检查占位符并构建启动。

常用命令：

```bash
./deploy.sh logs      # 跟踪日志
./deploy.sh ps        # 查看容器状态
./deploy.sh restart   # 重启容器
./deploy.sh down      # 停止并删除容器（data/ 数据保留）
./deploy.sh update    # 改完代码后重新构建并强制重建容器
```

也可以直接使用 Docker Compose：

```bash
docker-compose up -d
```

服务将在后台运行，默认地址：

```text
http://localhost:8080/
```

容器会自动挂载以下目录/文件：

| 挂载项 | 说明 |
|--------|------|
| `./data:/app/data` | 持久化 `auth_store.json` / `capture_store.json`，避免容器重启后丢失数据 |
| `.env`（通过 `env_file`） | 注入环境变量，不将敏感信息打包进镜像 |

### 3. 手动使用 Docker 启动

```bash
# 构建镜像
docker build -t feishu-oauth-app .

# 运行容器（映射端口、挂载数据目录、加载环境变量）
docker run -d \
  --name feishu-oauth-app \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  feishu-oauth-app
```

### 4. 注意事项

- `.env` 文件不会被打包进 Docker 镜像（已配置 `.dockerignore`），请确保在宿主机上准备好该文件
- `data/` 通过 volume 挂载到容器外，删除容器不会丢失已保存的授权信息和抓取记录
- 如需修改端口，可调整 `docker-compose.yml` 中的 `ports` 映射（如 `"8888:8080"`）
- Ubuntu 服务器从零部署的完整步骤见 `DEPLOY_UBUNTU.md`；速查版见 `一键部署.md`

## 使用流程

### 第一步：授权

打开：

```text
http://localhost:8080/login
```

授权成功后：

- 程序会把 `access_token`、`refresh_token`、用户信息写入本地 JSON 文件
- 响应中会返回 `scope`、`has_offline_access`、`has_drive_search_scope` 等信息

### 第二步：在首页前端选择用户并操作

打开首页：

```text
http://localhost:8080/
```

页面会自动读取本地已授权用户并填充到下拉框中。你可以：

- 先点击“新增授权用户”继续添加新用户
- 在下拉框里选择某个已授权用户（支持输入关键词过滤）
- 点击“刷新当前用户 token”或“刷新全部 token”
- 输入关键词并点击“开始搜索”
- 输入源文档和目标文件夹 token，点击“读取并复制到文件夹”
- 搜索通讯录成员，发送授权邀请或把成员加入抓取用户组

前端下拉框展示的是用户名，但提交给后端的是该用户的 `user_key`，这样比按 `name` 传参更稳定。

### 第三步：查看本地已保存用户

```text
http://localhost:8080/users
```

### 第四步：通过接口直接搜索云文档

搜索接口必须显式传入 `user_key`（例如 open_id），不会再默认使用最近一次授权成功的用户，也不会用 `name` 查找用户。默认只返回该用户**名下**的文档（请求侧传 `owner_ids` + 本地按 `owner_id` 二次过滤，因为搜索接口对 `owner_ids` 不保证生效）；结果中每条带 `is_owner` 标注：

```text
http://localhost:8080/search?q=项目&user_key=ou_xxx
```

查看该用户可见的全部文档（含他人创建但共享的）：

```text
http://localhost:8080/search?q=项目&user_key=ou_xxx&owner_only=false
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

### 第五步：复制文档到文件夹

通过接口复制源 docx 文档的纯文本内容到新文件夹：

```bash
curl -X POST http://localhost:8080/docx/clone-plain-text \
  -H "Content-Type: application/json" \
  -d '{
    "user_key": "ou_xxx",
    "source_document_id": "dox_xxx",
    "target_folder_token": "fldcn_xxx",
    "title": "复制后的文档标题"
  }'
```

`source_document_id` 也可以直接粘贴飞书文档链接，后端会自动提取 document_id。

当前版本会复制源 docx 的纯文本内容，不复制图片、表格样式或复杂块结构。

### 第六步：获取会议纪要建议文件名

复制会议纪要类文档前，可以先获取根据文档内容自动生成的建议标题（前端在输入源文档后会自动填充）：

```text
http://localhost:8080/docx/minutes-meta?user_key=ou_xxx&source_document_id=dox_xxx
```

返回的 `meta.suggested_filename` 形如 `张三_20260915_1430`，由用户名和从文档头部解析出的录制时间拼接而成。

### 第七步：搜索通讯录并发送授权邀请

#### 7.1 直接搜索通讯录成员

```bash
curl -X POST http://localhost:8080/invite/search-users \
  -H "Content-Type: application/json" \
  -d '{"q": "张三"}'
```

#### 7.2 查看已缓存的通讯录

```text
http://localhost:8080/invite/contacts?limit=500
```

#### 7.3 手动刷新通讯录缓存

```bash
curl -X POST http://localhost:8080/invite/contacts/refresh
```

#### 7.4 发送授权邀请消息

```bash
curl -X POST http://localhost:8080/invite/send \
  -H "Content-Type: application/json" \
  -d '{
    "open_id": "ou_xxx",
    "name": "张三",
    "message": "请完成授权"
  }'
```

也可以直接打开独立的邀请页面分享给同事：

```text
http://localhost:8080/invite
```

### 第八步：指定用户内容抓取

抓取功能面向“录制文字记录”场景：把要跟踪的同事加入抓取用户组后，程序会定时（或手动触发）搜索该用户新增的标题含“文字记录”的文档，读取纯文本内容，按 `姓名_录制时间` 命名复制到 `CAPTURE_TARGET_FOLDER_TOKEN` 指定的文件夹，并记录已处理文件避免重复抓取。

#### 8.1 查看 / 添加 / 移除抓取目标

```bash
# 查看当前抓取用户组
curl http://localhost:8080/capture/targets

# 添加（通常由前端从通讯录搜索结果中一键加入）
curl -X POST http://localhost:8080/capture/targets \
  -H "Content-Type: application/json" \
  -d '{"user": {"name": "张三", "open_id": "ou_xxx"}}'

# 移除
curl -X DELETE http://localhost:8080/capture/targets/<target_key>
```

#### 8.2 立即执行一次抓取

```bash
curl -X POST http://localhost:8080/capture/run \
  -H "Content-Type: application/json" \
  -d '{}'
```

默认**异步执行**：接口立即返回 `capture started`，进度与结果通过 `GET /capture/status` 查询（running 标志 / 最近一轮摘要 / 连续失败次数，可作为监控告警挂点），前端会自动轮询。需要同步等待完整结果可传 `{"sync": true}`。

#### 8.2.1 查询抓取状态

```bash
curl http://localhost:8080/capture/status
```

#### 8.3 查看历史抓取记录

```text
http://localhost:8080/capture/runs
```

> 运行抓取前必须先配置 `CAPTURE_TARGET_FOLDER_TOKEN`。每个抓取目标优先使用其本人在本地已授权的 token，否则回退到请求指定的 `user_key` 或本地第一个已授权用户。

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

抓取相关数据（抓取用户组、已处理文件、运行记录）保存在 `data/capture_store.json`。

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
   - 文档搜索结果列表（带可直接打开的文档链接）

## 手动刷新 token 现在是怎么运行的

`/users/refresh-token` 的执行流程如下：

1. 从 JSON 请求体读取 `user_key`
2. 按 `user_key` 读取本地保存的用户 token
3. 使用该用户的 `refresh_token` 调用飞书刷新接口
4. 把新的 token 信息回写到本地 JSON
5. 返回新的 token 过期时间、scope 和保存时间，不返回真实 token 值

另有 `/users/refresh-tokens` 一次性刷新所有本地用户；后台线程也会按 `TOKEN_REFRESH_SECONDS` 间隔自动批量刷新。

## Docx 克隆接口现在是怎么运行的

`/docx/clone-plain-text` 的执行流程如下：

1. 从 JSON 请求体读取：
   - `user_key`：必填，用于获取有效的 access_token
   - `source_document_id`：必填，支持直接粘贴 docx 链接，后端会自动提取 document_id
   - `target_folder_token`：必填，目标文件夹 token
   - `title`：可选，新文档标题，留空则使用 `Copied document`

2. 检查并确保 token 有效（同搜索接口的自动刷新逻辑）

3. 调用飞书接口：
   - 使用 `user_access_token` 读取源文档的 `raw_content`
   - 使用 `user_access_token` 在目标文件夹创建新文档
   - 将纯文本按段落拆分为 text block，分批写入新文档

4. 返回结果：
   - 源文档 ID、目标文件夹 token、新文档 ID
   - 原始内容长度、实际创建的 block 数量

> 当前版本仅复制纯文本内容，不保留图片、表格样式或复杂块结构。

## 内容抓取现在是怎么运行的

`/capture/run`（以及后台定时任务）的执行流程如下：

1. 从 `capture_store.json` 读取抓取用户组（targets）
2. 对每个目标用户：
   - 优先使用该用户本人在本地的 OAuth token，否则回退到默认已授权用户
   - 以 `CAPTURE_SEARCH_KEYWORD`（默认“文字记录”）为关键词、以该用户为 owner 搜索 doc/docx 文档（搜索接口的 owner 过滤对 user token 不可靠，程序会在本地按 owner_id 二次过滤）
   - 跳过标题不含“文字记录”或已处理过的文件
3. 对每个新文件：
   - 读取 `raw_content`，从文档头部解析录制时间，生成 `姓名_yyyyMMdd_HHmm` 标题
   - 将纯文本内容复制到 `CAPTURE_TARGET_FOLDER_TOKEN` 指定的文件夹
   - 在 `capture_store.json` 标记已处理，避免重复抓取
4. 把本轮运行的统计（created / skipped / failed / 每个目标的明细）追加到运行记录中

后台调度线程按 `CAPTURE_REFRESH_SECONDS`（最小 60 秒）间隔自动执行；`CAPTURE_STARTUP_REFRESH=true` 时启动后立即先跑一轮。同一时刻只允许一个抓取任务运行。

## 通讯录搜索与邀请现在是怎么运行的

通讯录数据依赖 `tenant_access_token`（应用级凭证），通过以下流程获取并缓存：

1. 获取 tenant_access_token
2. 获取应用可见的通讯录范围（`contact/v3/scopes`）
3. 遍历范围内的部门及其子部门，拉取所有成员
4. 去重、排序后存入内存缓存
5. 启动后台定时线程，按 `CONTACT_CACHE_REFRESH_SECONDS` 间隔自动刷新

### 接口说明

- `POST /invite/search-users`：在缓存中按关键词匹配成员姓名、英文名、邮箱、手机号、user_id、open_id、union_id
- `GET /invite/contacts`：直接返回已缓存的通讯录列表，支持 `limit` / `offset` 分页
- `POST /invite/contacts/refresh`：强制立即刷新通讯录缓存
- `POST /invite/send`：向指定用户发送一条飞书消息，内容为 OAuth 授权链接

## 前端页面现在是怎么运行的

首页 `/` 会渲染一个内嵌 HTML 页面（访问前需通过 `/front-login` 密码验证）。页面加载后会自动请求 `/users`、`/invite/contacts`、`/capture/targets` 填充各个选择框和列表。

页面包含五个主要面板：

1. **授权与分享**：新增授权用户按钮、授权链接复制、邀请文案复制
2. **通讯录搜索与邀请**：搜索成员、选择成员、编辑消息、发送授权邀请、加入抓取用户组
3. **指定用户内容抓取**：查看/移除抓取用户组成员、立即抓取新增文字记录
4. **搜索面板**：选择已授权用户（支持过滤）、输入关键词和文档类型、开始搜索、刷新 token
5. **复制文档到文件夹**：输入源文档链接/ID（自动填充建议标题）、目标文件夹 token、新标题，读取并纯文本复制

点击对应按钮后，前端通过 `fetch` 调用后端接口，并把返回的 JSON 直接显示在页面下方的结果区域。

## 后续扩展建议

你后面可以直接在这个结构上加：

- Feishu 文档富文本读取（表格、图片、块结构重建）
- 多维表格读写
- Slides / Sheets 操作
- SQLite / MySQL / Redis 持久化
- 更细粒度的登录态与权限管理

推荐扩展方式：

- 新接口能力放到 `app/services/` 里
- 新路由放到 `app/routes/` 里
- 本地文件存储替换数据库时，只需要替换 `app/storage/` 层

## 安全提醒

- 不要把 `APP_SECRET` 提交到 Git
- 不要把真实 token 文件提交到 Git
- 部署到服务器前务必修改 `FRONTEND_USERNAME`、`FRONTEND_PASSWORD` 和 `SESSION_SECRET_KEY`，不要使用默认值
- 正式环境建议加密存储 token，或改用数据库 / 密钥管理服务
- 本项目当前更适合本地开发和内网工具；如需暴露到公网，请配合 HTTPS、反向代理和访问控制使用
