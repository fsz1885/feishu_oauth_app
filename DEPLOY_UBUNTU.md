# Ubuntu Docker 部署

## 1. 安装 Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 2. 上传并解压

```bash
mkdir -p /opt/feishu_oauth_app
tar -xzf feishu_oauth_app_ubuntu.tar.gz -C /opt/feishu_oauth_app --strip-components=1
cd /opt/feishu_oauth_app
```

## 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

至少需要配置：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_REDIRECT_URI=http://your-domain-or-ip:8080/callback
FRONTEND_PASSWORD=换成你自己的强密码
SESSION_SECRET_KEY=replace_with_a_long_random_string
CAPTURE_TARGET_FOLDER_TOKEN=目标飞书文件夹token
```

### HTTPS 部署（推荐，Caddy + Let's Encrypt）

生产环境建议使用 Caddy 反向代理，自动申请并续期免费 HTTPS 证书。配置文件已自带：`deploy/caddy/Caddyfile`。

1. 域名 A 记录指向服务器公网 IP，云安全组放行 **80/443**
2. 编辑 `deploy/caddy/Caddyfile`，把 `mkt.gemdalesh.cn` 换成你的域名；同时确认 `reverse_proxy` 的目标端口与 `docker-compose.yml` 宿主机端口映射左侧一致（默认 `8080`，当前生产实例为 `3011`）
3. 启动 Caddy（host 网络，证书数据持久化）：

```bash
mkdir -p /opt/caddy-data /opt/caddy-config
docker run -d --name feishu-caddy --network host --restart unless-stopped \
  -v $PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v /opt/caddy-data:/data -v /opt/caddy-config:/config \
  caddy:2-alpine
```

4. `.env` 同步改为域名地址：`FEISHU_REDIRECT_URI=https://你的域名/callback`、`PUBLIC_BASE_URL=https://你的域名`，然后重建应用容器：

```bash
sudo docker compose up -d --build --force-recreate
```

5. 飞书开发者后台「安全设置」中新增重定向 URL：`https://你的域名/callback`

不使用 Caddy、自行用 Nginx 等其他反代时同理：`FEISHU_REDIRECT_URI` 要写外部可访问的回调地址，例如：

```env
FEISHU_REDIRECT_URI=https://your-domain.com/callback
```

并且飞书开发者后台里的回调地址必须完全一致。

## 4. 启动

```bash
sudo docker compose up -d --build
sudo docker compose logs -f
```

访问：

```text
http://your-domain-or-ip:8080/
```

## 5. 更新部署

上传新版压缩包后：

```bash
cd /opt/feishu_oauth_app
sudo docker compose down
sudo docker compose up -d --build --force-recreate
```

`data/` 目录会挂载在宿主机，里面保存授权 token、指定抓取用户表、已处理抓取记录。不要提交或公开这个目录。
