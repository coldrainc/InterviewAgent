#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aivago/InterviewAgent}"
API_SERVICE="${API_SERVICE:-interview-agent-api}"
WEB_API_URL="${WEB_API_URL:-https://api.aivago.cn}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"

cd "$APP_DIR"

log() {
  printf '\n\033[1;36m==> %s\033[0m\n' "$1"
}

run_git_pull() {
  if [[ "$SKIP_GIT_PULL" == "1" ]]; then
    log "跳过 git pull"
    return
  fi
  log "拉取最新代码"
  git pull origin main
}

ensure_backend_env() {
  if [[ ! -f .env ]]; then
    echo "缺少 $APP_DIR/.env，请先创建生产环境配置。" >&2
    exit 1
  fi
  if [[ ! -x .venv/bin/python ]]; then
    log "创建 Python 虚拟环境"
    python3 -m venv .venv
  fi
}

deploy_backend() {
  ensure_backend_env
  log "安装/更新后端依赖"
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e "backend[dev]"

  log "执行数据库迁移"
  cd "$APP_DIR/backend"
  ../.venv/bin/alembic upgrade head
  cd "$APP_DIR"

  log "重启后端服务：$API_SERVICE"
  sudo systemctl daemon-reload
  sudo systemctl restart "$API_SERVICE"
  sudo systemctl status "$API_SERVICE" --no-pager -l
}

deploy_frontend() {
  log "安装/更新前端依赖"
  cd "$APP_DIR/apps/desktop"
  if [[ -d node_modules ]]; then
    npm install --ignore-scripts
  else
    npm install --ignore-scripts
  fi

  log "重新构建 Web 前端"
  rm -rf dist
  VITE_INTERVIEW_AGENT_API_URL="$WEB_API_URL" npm run build

  log "重载 Nginx"
  sudo nginx -t
  sudo systemctl reload nginx
  cd "$APP_DIR"
}

deploy_all() {
  run_git_pull
  deploy_backend
  deploy_frontend
}

show_status() {
  log "后端服务状态"
  sudo systemctl status "$API_SERVICE" --no-pager -l || true
  log "Nginx 配置检查"
  sudo nginx -t
  log "健康检查"
  curl -fsS "$WEB_API_URL/health" || true
  printf '\n'
}

choose_action() {
  cat <<'MENU'
请选择部署操作：
  1) 全部：git pull + 后端依赖/迁移/重启 + 前端构建/Nginx reload
  2) 只更新后端：依赖 + 迁移 + 重启服务
  3) 只更新前端：npm install + build + Nginx reload
  4) 只 git pull
  5) 查看状态
  0) 退出
MENU
  read -r -p "输入选项: " choice
  case "$choice" in
    1) deploy_all ;;
    2) run_git_pull; deploy_backend ;;
    3) run_git_pull; deploy_frontend ;;
    4) run_git_pull ;;
    5) show_status ;;
    0) exit 0 ;;
    *) echo "未知选项：$choice" >&2; exit 2 ;;
  esac
}

case "${1:-menu}" in
  menu) choose_action ;;
  all) deploy_all ;;
  backend) run_git_pull; deploy_backend ;;
  frontend) run_git_pull; deploy_frontend ;;
  pull) run_git_pull ;;
  status) show_status ;;
  *)
    cat <<USAGE >&2
用法：
  $0 menu       # 交互菜单
  $0 all        # 全量部署
  $0 backend    # 更新并重启后端
  $0 frontend   # 更新并构建前端
  $0 pull       # 只拉代码
  $0 status     # 查看状态

可选环境变量：
  APP_DIR=/opt/aivago/InterviewAgent
  API_SERVICE=interview-agent-api
  WEB_API_URL=https://api.aivago.cn
  SKIP_GIT_PULL=1
USAGE
    exit 2
    ;;
esac

