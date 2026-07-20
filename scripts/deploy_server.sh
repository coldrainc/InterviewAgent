#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aivago/InterviewAgent}"
API_SERVICE="${API_SERVICE:-interview-agent-api}"
WEB_API_URL="${WEB_API_URL:-/api}"
WEB_HEALTH_URL="${WEB_HEALTH_URL:-https://www.aivago.cn/api/health}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
FORCE_INSTALL_DEPS="${FORCE_INSTALL_DEPS:-0}"
DEPLOY_CACHE_DIR="${DEPLOY_CACHE_DIR:-$APP_DIR/.deploy-cache}"

cd "$APP_DIR"

log() {
  printf '\n\033[1;36m==> %s\033[0m\n' "$1"
}

fingerprint_files() {
  local files=("$@")
  local payload=""
  local file
  for file in "${files[@]}"; do
    if [[ -f "$file" ]]; then
      if command -v sha256sum >/dev/null 2>&1; then
        payload+="$file $(sha256sum "$file")"$'\n'
      elif command -v shasum >/dev/null 2>&1; then
        payload+="$file $(shasum -a 256 "$file")"$'\n'
      else
        payload+="$file $(cksum "$file")"$'\n'
      fi
    else
      payload+="$file missing"$'\n'
    fi
  done

  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$payload" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$payload" | shasum -a 256 | awk '{print $1}'
  else
    printf '%s' "$payload" | cksum | awk '{print $1}'
  fi
}

dependency_stamp_matches() {
  local name="$1"
  local fingerprint="$2"
  local stamp="$DEPLOY_CACHE_DIR/$name.sha256"
  [[ -f "$stamp" ]] && [[ "$(cat "$stamp")" == "$fingerprint" ]]
}

write_dependency_stamp() {
  local name="$1"
  local fingerprint="$2"
  mkdir -p "$DEPLOY_CACHE_DIR"
  printf '%s\n' "$fingerprint" > "$DEPLOY_CACHE_DIR/$name.sha256"
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
  local backend_deps_fingerprint
  backend_deps_fingerprint="$(fingerprint_files "$APP_DIR/backend/pyproject.toml")"
  if [[ "$FORCE_INSTALL_DEPS" == "1" ]] \
    || [[ ! -x .venv/bin/interview-agent ]] \
    || ! dependency_stamp_matches "backend-deps" "$backend_deps_fingerprint"; then
    log "安装/更新后端依赖"
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -e "backend[dev]"
    write_dependency_stamp "backend-deps" "$backend_deps_fingerprint"
  else
    log "后端依赖未变更，跳过安装"
  fi

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
  cd "$APP_DIR/apps/desktop"
  local frontend_deps_fingerprint
  frontend_deps_fingerprint="$(fingerprint_files "$APP_DIR/apps/desktop/package.json" "$APP_DIR/apps/desktop/package-lock.json")"
  if [[ "$FORCE_INSTALL_DEPS" == "1" ]] \
    || [[ ! -d node_modules ]] \
    || ! dependency_stamp_matches "frontend-deps" "$frontend_deps_fingerprint"; then
    log "安装/更新前端依赖"
    npm install --ignore-scripts
  else
    log "前端依赖未变更，跳过安装"
  fi
  write_dependency_stamp "frontend-deps" "$frontend_deps_fingerprint"

  log "重新构建 Web 前端"
  rm -rf dist
  VITE_INTERVIEW_AGENT_API_URL="$WEB_API_URL" npm run build

  log "重载 Nginx"
  sudo nginx -t
  sudo systemctl reload nginx
  cd "$APP_DIR"
}

configure_nginx() {
  log "配置 Nginx Web 同源代理"
  sudo \
    APP_DIR="$APP_DIR" \
    WEB_DOMAIN="${WEB_DOMAIN:-www.aivago.cn}" \
    WEB_ROOT="${WEB_ROOT:-$APP_DIR/apps/desktop/dist}" \
    API_UPSTREAM="${API_UPSTREAM:-http://127.0.0.1:8020}" \
    AUTO_DISABLE_DEFAULT_WWW="${AUTO_DISABLE_DEFAULT_WWW:-0}" \
    "$APP_DIR/scripts/configure_nginx_web.sh"
}

configure_security() {
  log "配置服务器安全加固：Nginx WAF/限流 + fail2ban"
  sudo "$APP_DIR/scripts/configure_security_hardening.sh"
}

deploy_all() {
  run_git_pull
  deploy_backend
  deploy_frontend
  configure_nginx
}

show_status() {
  log "后端服务状态"
  sudo systemctl status "$API_SERVICE" --no-pager -l || true
  log "Nginx 配置检查"
  sudo nginx -t
  log "健康检查"
  curl -fsS "$WEB_HEALTH_URL" || true
  printf '\n'
}

choose_action() {
  cat <<'MENU'
请选择部署操作：
  1) 全部：git pull + 后端依赖按需安装/迁移/重启 + 前端依赖按需安装/构建 + Nginx 配置/reload
  2) 只更新后端：依赖按需安装 + 迁移 + 重启服务
  3) 只更新前端：依赖按需安装 + build + Nginx reload
  4) 配置 Nginx：www.aivago.cn + /api 同源代理
  5) 安全加固：Nginx WAF/限流 + fail2ban
  6) 只 git pull
  7) 查看状态
  0) 退出
MENU
  read -r -p "输入选项: " choice
  case "$choice" in
    1) deploy_all ;;
    2) run_git_pull; deploy_backend ;;
    3) run_git_pull; deploy_frontend ;;
    4) configure_nginx ;;
    5) configure_security ;;
    6) run_git_pull ;;
    7) show_status ;;
    0) exit 0 ;;
    *) echo "未知选项：$choice" >&2; exit 2 ;;
  esac
}

case "${1:-menu}" in
  menu) choose_action ;;
  all) deploy_all ;;
  backend) run_git_pull; deploy_backend ;;
  frontend) run_git_pull; deploy_frontend ;;
  nginx) configure_nginx ;;
  security) configure_security ;;
  pull) run_git_pull ;;
  status) show_status ;;
  *)
    cat <<USAGE >&2
用法：
  $0 menu       # 交互菜单
  $0 all        # 全量部署
  $0 backend    # 更新并重启后端
  $0 frontend   # 更新并构建前端
  $0 nginx      # 配置 Nginx Web 同源代理
  $0 security   # 配置 Nginx WAF/限流 + fail2ban
  $0 pull       # 只拉代码
  $0 status     # 查看状态

可选环境变量：
  APP_DIR=/opt/aivago/InterviewAgent
  API_SERVICE=interview-agent-api
  WEB_API_URL=/api
  WEB_HEALTH_URL=https://www.aivago.cn/api/health
  AUTO_DISABLE_DEFAULT_WWW=1
  SKIP_GIT_PULL=1
  FORCE_INSTALL_DEPS=1
USAGE
    exit 2
    ;;
esac
