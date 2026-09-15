#!/usr/bin/env bash
#
# Feishu OAuth App —— 一键部署脚本 (Docker)
#
# 用法:
#   ./deploy.sh            构建并后台启动 (首次部署 / 修改代码后)
#   ./deploy.sh logs       跟踪日志
#   ./deploy.sh ps         查看容器状态
#   ./deploy.sh restart    重启容器
#   ./deploy.sh down       停止并删除容器
#   ./deploy.sh update     重新构建并强制重建容器 (更新部署)
#
set -euo pipefail

cd "$(dirname "$0")"

# ---------- 输出着色 ----------
c_info() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m[ok]\033[0m    %s\n' "$*"; }
c_warn() { printf '\033[1;33m[warn]\033[0m  %s\n' "$*" >&2; }
c_err()  { printf '\033[1;31m[err]\033[0m   %s\n' "$*" >&2; }

# ---------- 1. 检测 docker compose ----------
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  c_err "未检测到 docker compose。请先安装 Docker (含 compose 插件):"
  cat <<'EOF'
  # Ubuntu / Debian 示例:
  sudo apt update
  sudo apt install -y ca-certificates curl gnupg
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"   # 之后重新登录以免 sudo
EOF
  exit 1
fi
c_info "使用: $DC"

# ---------- 2. 保证 .env 存在 ----------
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    c_ok "已从 .env.example 生成 .env"
  else
    c_err "缺少 .env 且未找到 .env.example 模板，无法继续。"
    exit 1
  fi
fi

# ---------- 3. 检查是否仍是占位符 (未填写真实配置) ----------
check_placeholder() {
  local bad=0
  grep -qE '^FEISHU_APP_ID=(cli_xxx|cli_xxxxxxxxxxxxx)' .env && bad=1
  grep -qE '^FEISHU_APP_SECRET=replace_me' .env && bad=1
  if [ "$bad" = "1" ]; then
    c_warn "检测到 .env 里仍是模板占位符 (FEISHU_APP_ID / FEISHU_APP_SECRET 未填写)。"
    c_warn "请先编辑 .env 填入真实飞书应用凭据，否则容器启动会失败。"
    printf "是否仍然继续构建? [y/N] "
    read -r ans
    case "${ans,,}" in
      y|yes) c_warn "继续构建 (预计应用会启动失败，请稍后修改 .env 再 ./deploy.sh restart)" ;;
      *) c_info "已取消。请编辑 .env 后重新运行 ./deploy.sh"; exit 0 ;;
    esac
  fi
}

# ---------- 4. 保证 data 目录存在 (宿主机挂载点) ----------
mkdir -p data

ACTION="${1:-up}"

case "$ACTION" in
  up)
    check_placeholder
    c_info "构建并启动容器..."
    $DC up -d --build
    sleep 2
    c_info "容器状态:"
    $DC ps
    # 推导访问端口
    PORT="$(grep -E '^APP_PORT=' .env | head -1 | cut -d= -f2 || true)"
    PORT="${PORT:-8080}"
    cat <<EOF

启动完成。访问地址:
  http://<你的服务器IP或域名>:${PORT}/

查看日志:    ./deploy.sh logs
停止服务:    ./deploy.sh down
EOF
    ;;

  logs)
    $DC logs -f
    ;;

  ps|status)
    $DC ps
    ;;

  restart)
    $DC restart
    c_ok "已重启"
    $DC ps
    ;;

  down)
    $DC down
    c_ok "已停止并移除容器 (data/ 数据保留)"
    ;;

  update)
    c_info "重新构建并强制重建容器..."
    $DC up -d --build --force-recreate
    $DC ps
    ;;

  *)
    c_err "未知命令: $ACTION"
    echo "可用命令: up | logs | ps | restart | down | update"
    echo "  直接运行 ./deploy.sh 等同于 up"
    exit 1
    ;;
esac
