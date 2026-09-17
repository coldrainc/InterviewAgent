#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/deploy/compose.yml"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '错误：%s\n' "$*" >&2; exit 1; }

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

compose() {
  APP_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

env_value() {
  local key="$1" default_value="${2:-}"
  local value=""
  if [[ -f "$ENV_FILE" ]]; then
    value="$(sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1)"
  fi
  printf '%s' "${value:-$default_value}"
}

random_hex() {
  openssl rand -hex "$1"
}

legacy_postgres_password() {
  local password database_url
  password="$(container_env_value interview-agent-postgres POSTGRES_PASSWORD)"
  if [[ -n "$password" ]]; then
    printf '%s' "$password"
    return
  fi
  password="$(legacy_env_value POSTGRES_PASSWORD)"
  if [[ -n "$password" ]]; then
    printf '%s' "$password"
    return
  fi
  database_url="$(legacy_env_value DATABASE_URL)"
  if [[ "$database_url" =~ ://[^:]+:([^@]+)@ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
    return
  fi
  printf 'interview_agent'
}

legacy_env_value() {
  local key="$1" default_value="${2:-}" legacy_env="$ROOT_DIR/.env"
  local value=""
  if [[ -f "$legacy_env" ]]; then
    value="$(sed -n "s/^${key}=//p" "$legacy_env" | tail -n 1)"
  fi
  printf '%s' "${value:-$default_value}"
}

detect_volume() {
  local fallback="$1"
  shift
  local candidate
  for candidate in "$@"; do
    if docker volume inspect "$candidate" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return
    fi
  done
  printf '%s' "$fallback"
}

container_volume_for() {
  local container="$1" destination="$2"
  docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Name}}{{end}}{{end}}" \
    "$container" 2>/dev/null || true
}

container_env_value() {
  local container="$1" key="$2"
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$container" 2>/dev/null \
    | sed -n "s/^${key}=//p" | tail -n 1
}

init_env() {
  require_command docker
  require_command openssl
  if [[ -f "$ENV_FILE" ]]; then
    log "生产配置已存在，保持不变：$ENV_FILE"
    return
  fi

  local public_url="${PUBLIC_URL:-$(legacy_env_value PUBLIC_WEB_BASE_URL http://localhost:8080)}"
  local origin="${public_url%/}"
  local bind_address postgres_volume minio_volume qdrant_volume postgres_password minio_password
  if [[ "$origin" == https://* ]]; then
    bind_address="127.0.0.1"
  else
    bind_address="0.0.0.0"
  fi
  postgres_volume="$(container_volume_for interview-agent-postgres /var/lib/postgresql/data)"
  postgres_volume="${postgres_volume:-$(detect_volume postgres_data postgres_data interview_agent_postgres interviewagent_postgres_data)}"
  minio_volume="$(container_volume_for interview-agent-minio /data)"
  minio_volume="${minio_volume:-$(detect_volume minio_data minio_data interview_agent_minio interviewagent_minio_data)}"
  qdrant_volume="$(container_volume_for interview-agent-qdrant /qdrant/storage)"
  qdrant_volume="${qdrant_volume:-$(detect_volume qdrant_storage qdrant_storage interviewagent_qdrant_storage)}"
  if docker volume inspect "$postgres_volume" >/dev/null 2>&1; then
    postgres_password="$(legacy_postgres_password)"
  else
    postgres_password="$(random_hex 24)"
  fi
  if docker volume inspect "$minio_volume" >/dev/null 2>&1; then
    minio_password="$(container_env_value interview-agent-minio MINIO_ROOT_PASSWORD)"
    minio_password="${minio_password:-$(legacy_env_value OBJECT_STORAGE_SECRET_KEY interview_agent_password)}"
  else
    minio_password="$(random_hex 24)"
  fi

  umask 077
  cat > "$ENV_FILE" <<EOF
INTERVIEW_ENV=production
APP_BIND_ADDRESS=$bind_address
APP_PORT=${APP_PORT:-8080}
API_PORT=${API_PORT:-8020}
PUBLIC_WEB_BASE_URL=$origin
PUBLIC_API_BASE_URL=$origin/api
INTERVIEW_ALLOWED_ORIGINS=$origin

PYTHON_IMAGE=python:3.12-slim
TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
NODE_IMAGE=node:22-alpine
NGINX_IMAGE=nginx:1.27-alpine
POSTGRES_IMAGE=postgres:16-alpine
MINIO_IMAGE=minio/minio:RELEASE.2024-07-16T23-46-41Z
QDRANT_IMAGE=qdrant/qdrant:v1.11.5
BACKUP_HELPER_IMAGE=alpine:3.20

POSTGRES_DB=interview_agent
POSTGRES_USER=interview_agent
POSTGRES_PASSWORD=$postgres_password
MINIO_ROOT_USER=interview_agent
MINIO_ROOT_PASSWORD=$minio_password
OBJECT_STORAGE_BUCKET=interview-agent
QDRANT_COLLECTION=interview_agent

POSTGRES_VOLUME_NAME=$postgres_volume
MINIO_VOLUME_NAME=$minio_volume
QDRANT_VOLUME_NAME=$qdrant_volume
RUNTIME_VOLUME_NAME=interview_agent_runtime
MODEL_CACHE_VOLUME_NAME=interview_agent_model_cache

INTERVIEW_API_AUTH_REQUIRED=true
INTERVIEW_AUTH_TOKEN_SECRET=$(random_hex 32)
INTERVIEW_AUTH_DEV_LOGIN_ENABLED=false
INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED=false
INTERVIEW_ALLOW_MOCK_RECHARGE=false
INTERVIEW_PAYMENT_WEBHOOK_SECRET=$(random_hex 24)
INTERVIEW_DEFAULT_TENANT_ID=default

OPENAI_API_KEY=
GATEWAY_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=
DASHSCOPE_API_KEY=
ARK_API_KEY=
MOONSHOT_API_KEY=
XAI_API_KEY=
OPENAI_MODEL=gpt-5.5
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

INTERVIEW_TRIAL_USES=2
INTERVIEW_CREDIT_USD_RATE=100
INTERVIEW_MAX_RECHARGE_CREDITS=10000
INTERVIEW_MAX_UPLOAD_BYTES=5242880
INTERVIEW_MAX_MESSAGE_CHARS=8000
INTERVIEW_RATE_LIMIT_PER_MINUTE=60
INTERVIEW_STORE_UPLOAD_SOURCE_PATH=false
INTERVIEW_PROMPT_INJECTION_BLOCK_ENABLED=true
INTERVIEW_PROMPT_INJECTION_BLOCK_SCORE=70
INTERVIEW_UPLOAD_CONTENT_SCAN_ENABLED=true
INTERVIEW_UPLOAD_ANTIVIRUS_ENABLED=false
INTERVIEW_LOG_LEVEL=INFO
EOF
  chmod 600 "$ENV_FILE"
  log "已生成生产配置：$ENV_FILE"
  printf '请至少填写一个模型密钥，例如 DEEPSEEK_API_KEY。\n'
  if docker volume inspect "$postgres_volume" >/dev/null 2>&1; then
    printf '检测到旧数据卷，已沿用旧版存储凭据；完成升级后可安排单独的密码轮换。\n'
  fi
}

require_env() {
  [[ -f "$ENV_FILE" ]] || die "缺少 $ENV_FILE，请先运行：./deploy/stack.sh init"
  local required=(POSTGRES_PASSWORD MINIO_ROOT_PASSWORD INTERVIEW_AUTH_TOKEN_SECRET INTERVIEW_PAYMENT_WEBHOOK_SECRET)
  local key value
  for key in "${required[@]}"; do
    value="$(env_value "$key")"
    [[ -n "$value" && "$value" != replace-* ]] || die "$key 尚未配置"
  done
  [[ "$(env_value INTERVIEW_ENV)" == "production" ]] || die "INTERVIEW_ENV 必须为 production"
  [[ "$(env_value INTERVIEW_API_AUTH_REQUIRED)" == "true" ]] || die "生产环境必须开启 INTERVIEW_API_AUTH_REQUIRED"
  [[ "$(env_value INTERVIEW_AUTH_DEV_LOGIN_ENABLED)" == "false" ]] || die "生产环境必须关闭开发登录"
  [[ "$(env_value POSTGRES_PASSWORD)" =~ ^[A-Za-z0-9._-]+$ ]] \
    || die "POSTGRES_PASSWORD 只能包含字母、数字、点、下划线和连字符"
}

preflight_stack() {
  require_command docker
  require_command curl
  docker info >/dev/null 2>&1 || die "Docker daemon 不可用"
  docker compose version >/dev/null 2>&1 || die "需要 Docker Compose v2"
  require_env
  compose config --quiet
  local model_keys=(OPENAI_API_KEY GATEWAY_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY GOOGLE_API_KEY DEEPSEEK_API_KEY DASHSCOPE_API_KEY ARK_API_KEY MOONSHOT_API_KEY XAI_API_KEY)
  local key has_model_key=0
  for key in "${model_keys[@]}"; do
    if [[ -n "$(env_value "$key")" ]]; then
      has_model_key=1
      break
    fi
  done
  if [[ "$has_model_key" == "0" ]]; then
    printf '警告：未配置模型 API Key，系统可启动但 Agent 会使用离线降级回答。\n' >&2
  fi
}

legacy_service_stop() {
  local service="${LEGACY_API_SERVICE:-interview-agent-api}"
  if ! command -v systemctl >/dev/null 2>&1 || ! systemctl is-active --quiet "$service" 2>/dev/null; then
    return
  fi
  [[ "${STOP_LEGACY_SERVICES:-1}" == "1" ]] || die "旧服务 $service 正在运行并可能占用端口。设置 STOP_LEGACY_SERVICES=1 后重试。"
  log "停止旧版 systemd 服务：$service"
  if [[ "$(id -u)" == "0" ]]; then
    systemctl stop "$service"
  else
    sudo systemctl stop "$service"
  fi
}

legacy_service_disable() {
  local service="${LEGACY_API_SERVICE:-interview-agent-api}"
  command -v systemctl >/dev/null 2>&1 || return
  systemctl list-unit-files "$service.service" >/dev/null 2>&1 || return
  log "新版健康检查通过，禁用旧版 systemd 服务：$service"
  if [[ "$(id -u)" == "0" ]]; then
    systemctl disable "$service"
  else
    sudo systemctl disable "$service"
  fi
}

legacy_containers_stop() {
  local names=(interview-agent-postgres interview-agent-minio interview-agent-qdrant)
  local name
  for name in "${names[@]}"; do
    if [[ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" == "true" ]]; then
      log "停止旧版基础设施容器：$name"
      docker stop "$name" >/dev/null
    fi
  done
}

restore_legacy_after_failure() {
  local exit_code="$1"
  trap - EXIT ERR INT TERM
  printf '\n部署失败，正在恢复升级前仍在运行的旧服务...\n' >&2
  compose down --remove-orphans >/dev/null 2>&1 || true
  if [[ -n "${LAST_BACKUP_DIR:-}" && -d "$LAST_BACKUP_DIR" ]]; then
    printf '正在恢复本次发布前的数据快照：%s\n' "$LAST_BACKUP_DIR" >&2
    restore_volume "$(env_value POSTGRES_VOLUME_NAME postgres_data)" \
      "$LAST_BACKUP_DIR/$(env_value POSTGRES_VOLUME_NAME postgres_data).tar.gz" || true
    restore_volume "$(env_value MINIO_VOLUME_NAME minio_data)" \
      "$LAST_BACKUP_DIR/$(env_value MINIO_VOLUME_NAME minio_data).tar.gz" || true
    restore_volume "$(env_value QDRANT_VOLUME_NAME qdrant_storage)" \
      "$LAST_BACKUP_DIR/$(env_value QDRANT_VOLUME_NAME qdrant_storage).tar.gz" || true
    restore_volume "$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime)" \
      "$LAST_BACKUP_DIR/$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime).tar.gz" || true
  fi
  if [[ "${CURRENT_COMPOSE_WAS_RUNNING:-0}" == "1" ]]; then
    local app_tag="${ACTIVE_APP_IMAGE_TAG:-local}" image
    for image in backend embedding web; do
      if docker image inspect "interview-agent-${image}:rollback-before-deploy" >/dev/null 2>&1; then
        docker tag "interview-agent-${image}:rollback-before-deploy" \
          "interview-agent-${image}:${app_tag}" >/dev/null
      fi
    done
    compose up -d postgres minio qdrant embedding api web >/dev/null 2>&1 || true
  fi
  local name
  for name in ${LEGACY_RUNNING_CONTAINERS:-}; do
    docker start "$name" >/dev/null 2>&1 || true
  done
  if [[ "${LEGACY_SYSTEMD_WAS_ACTIVE:-0}" == "1" ]] && command -v systemctl >/dev/null 2>&1; then
    if [[ "$(id -u)" == "0" ]]; then
      systemctl start "${LEGACY_API_SERVICE:-interview-agent-api}" >/dev/null 2>&1 || true
    else
      sudo systemctl start "${LEGACY_API_SERVICE:-interview-agent-api}" >/dev/null 2>&1 || true
    fi
  fi
  printf '旧服务恢复流程已执行；本次部署退出码：%s\n' "$exit_code" >&2
  exit "$exit_code"
}

import_legacy_runtime() {
  local source="$ROOT_DIR/.interview_agent"
  local volume helper_image
  [[ -d "$source" ]] || return
  volume="$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime)"
  helper_image="$(env_value BACKUP_HELPER_IMAGE alpine:3.20)"
  docker volume create "$volume" >/dev/null
  if docker run --rm -v "$volume:/target:ro" "$helper_image" sh -c 'test -n "$(find /target -mindepth 1 -print -quit)"'; then
    return
  fi
  log "迁移旧版运行数据到持久化卷"
  docker run --rm \
    -v "$source:/source:ro" \
    -v "$volume:/target" \
    "$helper_image" sh -c 'cp -a /source/. /target/'
}

configure_host_proxy() {
  local public_url domain port
  public_url="$(env_value PUBLIC_WEB_BASE_URL)"
  [[ "$public_url" == https://* ]] || return
  [[ "${CONFIGURE_HOST_NGINX:-auto}" != "0" ]] || return
  command -v nginx >/dev/null 2>&1 || return
  domain="${public_url#https://}"
  domain="${domain%%/*}"
  port="$(env_value APP_PORT 8080)"
  [[ -f "/etc/letsencrypt/live/$domain/fullchain.pem" ]] || {
    [[ "${CONFIGURE_HOST_NGINX:-auto}" == "1" ]] && die "未找到 $domain 的 HTTPS 证书"
    return
  }
  log "切换现有域名到新版容器"
  sudo \
    APP_DIR="$ROOT_DIR" \
    WEB_DOMAIN="$domain" \
    WEB_UPSTREAM="http://127.0.0.1:$port" \
    API_UPSTREAM="http://127.0.0.1:$(env_value API_PORT 8020)" \
    AUTO_DISABLE_DEFAULT_WWW="${AUTO_DISABLE_DEFAULT_WWW:-0}" \
    "$ROOT_DIR/scripts/configure_nginx_web.sh"
}

wait_http() {
  local url="$1" attempts="${2:-60}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done
  die "健康检查超时：$url"
}

deploy_stack() {
  require_command docker
  require_command curl
  init_env
  preflight_stack

  local legacy_name legacy_running="" image
  ACTIVE_APP_IMAGE_TAG="$(env_value APP_IMAGE_TAG local)"
  CURRENT_COMPOSE_WAS_RUNNING=0
  if compose ps --status running api 2>/dev/null | grep -q api; then
    CURRENT_COMPOSE_WAS_RUNNING=1
    for image in backend embedding web; do
      if docker image inspect "interview-agent-${image}:${ACTIVE_APP_IMAGE_TAG}" >/dev/null 2>&1; then
        docker tag "interview-agent-${image}:${ACTIVE_APP_IMAGE_TAG}" \
          "interview-agent-${image}:rollback-before-deploy"
      fi
    done
  fi
  for legacy_name in interview-agent-postgres interview-agent-minio interview-agent-qdrant; do
    if [[ "$(docker inspect -f '{{.State.Running}}' "$legacy_name" 2>/dev/null || true)" == "true" ]]; then
      legacy_running+=" $legacy_name"
    fi
  done
  LEGACY_RUNNING_CONTAINERS="${legacy_running# }"
  LEGACY_SYSTEMD_WAS_ACTIVE=0
  if command -v systemctl >/dev/null 2>&1 \
    && systemctl is-active --quiet "${LEGACY_API_SERVICE:-interview-agent-api}" 2>/dev/null; then
    LEGACY_SYSTEMD_WAS_ACTIVE=1
  fi

  log "构建应用镜像（此阶段不停止当前服务）"
  compose pull postgres minio qdrant
  docker pull "$(env_value BACKUP_HELPER_IMAGE alpine:3.20)"
  compose build --pull api embedding web

  trap 'exit_code=$?; if [[ $exit_code -ne 0 ]]; then restore_legacy_after_failure "$exit_code"; fi' EXIT

  legacy_service_stop
  legacy_containers_stop
  if docker volume inspect "$(env_value POSTGRES_VOLUME_NAME postgres_data)" >/dev/null 2>&1; then
    BACKUP_NO_RESTART=1 backup_stack
  fi
  import_legacy_runtime

  log "启动数据库、对象存储、向量库和 Embedding 服务"
  compose up -d postgres minio qdrant embedding
  compose up --wait postgres minio

  log "执行数据库迁移"
  compose run --rm migration

  log "启动 API 与 Web"
  compose up -d api web
  local port
  port="$(env_value APP_PORT 8080)"
  wait_http "http://127.0.0.1:${port}/healthz"
  wait_http "http://127.0.0.1:${port}/api/health"
  legacy_service_disable

  if ! compose exec -T api test -f /app/.interview_agent/rag_index.json; then
    log "首次部署：构建基础 RAG 索引"
    compose --profile tools run --rm indexer
  fi

  configure_host_proxy

  trap - EXIT ERR INT TERM
  for image in backend embedding web; do
    docker image rm "interview-agent-${image}:rollback-before-deploy" >/dev/null 2>&1 || true
  done

  log "部署完成"
  compose ps
  printf '\n访问地址：%s\n' "$(env_value PUBLIC_WEB_BASE_URL "http://127.0.0.1:${port}")"
}

archive_volume() {
  local volume="$1" output="$2"
  local helper_image
  docker volume inspect "$volume" >/dev/null 2>&1 || return 0
  helper_image="$(env_value BACKUP_HELPER_IMAGE alpine:3.20)"
  docker run --rm \
    -v "$volume:/source:ro" \
    -v "$output:/backup" \
    "$helper_image" sh -c "cd /source && tar czf /backup/${volume}.tar.gz ."
}

backup_stack() {
  require_command docker
  require_env
  local stamp backup_dir was_running=0
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup_dir="$BACKUP_ROOT/$stamp"
  mkdir -p "$backup_dir"
  chmod 700 "$BACKUP_ROOT" "$backup_dir"

  if compose ps --status running postgres 2>/dev/null | grep -q postgres; then
    was_running=1
    log "暂停应用写入"
    compose stop web api embedding >/dev/null 2>&1 || true
    log "导出 PostgreSQL"
    compose exec -T postgres pg_dump \
      -U "$(env_value POSTGRES_USER interview_agent)" \
      -d "$(env_value POSTGRES_DB interview_agent)" \
      --clean --if-exists > "$backup_dir/postgres.sql"
    compose stop qdrant minio postgres >/dev/null
  fi

  log "归档持久化卷"
  archive_volume "$(env_value POSTGRES_VOLUME_NAME postgres_data)" "$backup_dir"
  archive_volume "$(env_value MINIO_VOLUME_NAME minio_data)" "$backup_dir"
  archive_volume "$(env_value QDRANT_VOLUME_NAME qdrant_storage)" "$backup_dir"
  archive_volume "$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime)" "$backup_dir"
  if [[ -d "$ROOT_DIR/.interview_agent" ]]; then
    tar czf "$backup_dir/legacy-runtime.tar.gz" -C "$ROOT_DIR" .interview_agent
  fi
  cp "$ENV_FILE" "$backup_dir/env.production"
  chmod 600 "$backup_dir/env.production"
  {
    printf 'created_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'git_revision=%s\n' "$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  } > "$backup_dir/manifest.txt"
  LAST_BACKUP_DIR="$backup_dir"

  if [[ "$was_running" == "1" && "${BACKUP_NO_RESTART:-0}" != "1" ]]; then
    log "恢复服务"
    compose up -d postgres minio qdrant embedding api web
  fi
  log "备份完成：$backup_dir"
}

restore_volume() {
  local volume="$1" archive="$2"
  local helper_image
  [[ -f "$archive" ]] || return 0
  helper_image="$(env_value BACKUP_HELPER_IMAGE alpine:3.20)"
  docker volume create "$volume" >/dev/null
  docker run --rm \
    -v "$volume:/target" \
    -v "$(dirname "$archive"):/backup:ro" \
    "$helper_image" sh -c "rm -rf /target/* /target/.[!.]* /target/..?* 2>/dev/null || true; tar xzf /backup/$(basename "$archive") -C /target"
}

restore_stack() {
  local backup_dir="${1:-}"
  [[ -n "$backup_dir" && -d "$backup_dir" ]] || die "用法：RESTORE_CONFIRM=YES ./deploy/stack.sh restore backups/<时间>"
  [[ "${RESTORE_CONFIRM:-}" == "YES" ]] || die "恢复会覆盖当前数据，请设置 RESTORE_CONFIRM=YES"
  require_env
  log "停止当前服务"
  compose down
  restore_volume "$(env_value POSTGRES_VOLUME_NAME postgres_data)" "$backup_dir/$(env_value POSTGRES_VOLUME_NAME postgres_data).tar.gz"
  restore_volume "$(env_value MINIO_VOLUME_NAME minio_data)" "$backup_dir/$(env_value MINIO_VOLUME_NAME minio_data).tar.gz"
  restore_volume "$(env_value QDRANT_VOLUME_NAME qdrant_storage)" "$backup_dir/$(env_value QDRANT_VOLUME_NAME qdrant_storage).tar.gz"
  restore_volume "$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime)" "$backup_dir/$(env_value RUNTIME_VOLUME_NAME interview_agent_runtime).tar.gz"
  log "恢复完成，重新启动服务"
  compose up -d postgres minio qdrant embedding api web
}

status_stack() {
  require_env
  compose ps
  local port
  port="$(env_value APP_PORT 8080)"
  printf '\nWeb: '
  curl -fsS "http://127.0.0.1:${port}/healthz" || true
  printf 'API: '
  curl -fsS "http://127.0.0.1:${port}/api/health" || true
  printf '\n'
}

case "${1:-help}" in
  init) init_env ;;
  deploy|update) deploy_stack ;;
  backup) backup_stack ;;
  restore) restore_stack "${2:-}" ;;
  index) require_env; compose --profile tools run --rm vector-indexer ;;
  preflight) init_env; preflight_stack; printf '部署前检查通过。\n' ;;
  doctor) require_env; compose exec -T api interview-agent doctor ;;
  status) status_stack ;;
  logs) require_env; compose logs -f --tail=200 "${2:-api}" ;;
  restart) require_env; compose restart api web ;;
  down) require_env; compose down ;;
  *)
    cat <<'USAGE'
Interview Agent 单服务器部署

  ./deploy/stack.sh init                 生成生产配置和随机密钥
  ./deploy/stack.sh deploy               首次部署或安全升级
  ./deploy/stack.sh status               查看容器与健康状态
  ./deploy/stack.sh logs [api|web|...]   查看日志
  ./deploy/stack.sh backup               一致性备份全部业务数据
  RESTORE_CONFIRM=YES ./deploy/stack.sh restore backups/<时间>
  ./deploy/stack.sh index                重建 RAG 索引
  ./deploy/stack.sh preflight            检查生产配置和 Compose
  ./deploy/stack.sh restart              重启 API 和 Web
  ./deploy/stack.sh down                 停止服务但保留所有数据

首次初始化可指定：
  PUBLIC_URL=https://example.com ./deploy/stack.sh init
USAGE
    ;;
esac
