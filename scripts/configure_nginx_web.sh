#!/usr/bin/env bash
set -euo pipefail

WEB_DOMAIN="${WEB_DOMAIN:-www.aivago.cn}"
APP_DIR="${APP_DIR:-/opt/aivago/InterviewAgent}"
WEB_ROOT="${WEB_ROOT:-$APP_DIR/apps/desktop/dist}"
API_UPSTREAM="${API_UPSTREAM:-http://127.0.0.1:8020}"
CONFIG_NAME="${CONFIG_NAME:-aivago-web}"
SITES_AVAILABLE="${SITES_AVAILABLE:-/etc/nginx/sites-available}"
SITES_ENABLED="${SITES_ENABLED:-/etc/nginx/sites-enabled}"
SITES_DISABLED="${SITES_DISABLED:-/etc/nginx/sites-disabled}"
CERT_DIR="${CERT_DIR:-/etc/letsencrypt/live/$WEB_DOMAIN}"
AUTO_DISABLE_DEFAULT_WWW="${AUTO_DISABLE_DEFAULT_WWW:-0}"

CONFIG_PATH="$SITES_AVAILABLE/$CONFIG_NAME"
ENABLED_PATH="$SITES_ENABLED/$CONFIG_NAME"
DEFAULT_ENABLED="$SITES_ENABLED/default"
CONFIG_CHANGED=0

log() {
  printf '\n\033[1;36m==> %s\033[0m\n' "$1"
}

die() {
  echo "错误：$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "请用 sudo 执行：sudo $0"
  fi
}

check_inputs() {
  [[ -d "$WEB_ROOT" ]] || die "前端目录不存在：$WEB_ROOT，请先构建前端。"
  [[ -f "$CERT_DIR/fullchain.pem" ]] || die "证书不存在：$CERT_DIR/fullchain.pem，请先为 $WEB_DOMAIN 申请 HTTPS 证书。"
  [[ -f "$CERT_DIR/privkey.pem" ]] || die "证书私钥不存在：$CERT_DIR/privkey.pem"
}

backup_existing_config() {
  if [[ -f "$CONFIG_PATH" ]]; then
    local backup="$CONFIG_PATH.bak.$(date +%Y%m%d%H%M%S)"
    cp "$CONFIG_PATH" "$backup"
    echo "已备份旧配置：$backup"
  fi
}

render_config() {
  local target="$1"
  cat > "$target" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $WEB_DOMAIN;

    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $WEB_DOMAIN;

    root $WEB_ROOT;
    index index.html;
    client_max_body_size 10m;

    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location ~ ^/api/(sessions/[^/]+/stream)$ {
        rewrite ^/api/(.*)$ /\$1 break;
        proxy_pass $API_UPSTREAM;
        proxy_http_version 1.1;

        proxy_set_header Host api.aivago.cn;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Request-ID \$request_id;
        proxy_set_header Connection "";
        proxy_set_header Accept-Encoding "";

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_read_timeout 600;
        proxy_connect_timeout 60;
        proxy_send_timeout 600;

        add_header X-Accel-Buffering no always;
        add_header Cache-Control "no-cache, no-transform" always;
    }

    location /api/ {
        proxy_pass $API_UPSTREAM/;
        proxy_http_version 1.1;

        proxy_set_header Host api.aivago.cn;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Request-ID \$request_id;
        proxy_set_header Connection "";
        proxy_set_header Accept-Encoding "";

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        proxy_read_timeout 600;
        proxy_connect_timeout 60;
        proxy_send_timeout 600;

        add_header X-Accel-Buffering no always;
    }

    location /assets/ {
        try_files \$uri =404;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX
}

write_config_if_changed() {
  local tmp_config
  tmp_config="$(mktemp)"
  render_config "$tmp_config"

  if [[ -f "$CONFIG_PATH" ]] && cmp -s "$tmp_config" "$CONFIG_PATH"; then
    rm -f "$tmp_config"
    echo "Nginx Web 配置未变更，跳过写入和备份。"
    return
  fi

  backup_existing_config
  mv "$tmp_config" "$CONFIG_PATH"
  chmod 644 "$CONFIG_PATH"
  CONFIG_CHANGED=1
  echo "已写入 Nginx Web 配置：$CONFIG_PATH"
}

enable_config() {
  if [[ -L "$ENABLED_PATH" ]] && [[ "$(readlink "$ENABLED_PATH")" == "$CONFIG_PATH" ]]; then
    return
  fi
  ln -sfn "$CONFIG_PATH" "$ENABLED_PATH"
  CONFIG_CHANGED=1
}

maybe_disable_default_conflict() {
  if [[ ! -e "$DEFAULT_ENABLED" ]]; then
    return
  fi

  if ! grep -q "server_name .*${WEB_DOMAIN//./\\.}" "$DEFAULT_ENABLED"; then
    return
  fi

  if [[ "$AUTO_DISABLE_DEFAULT_WWW" == "1" ]]; then
    mkdir -p "$SITES_DISABLED"
    local backup="$SITES_DISABLED/default.disabled.$(date +%Y%m%d%H%M%S)"
    mv "$DEFAULT_ENABLED" "$backup"
    CONFIG_CHANGED=1
    echo "已禁用冲突的 default 配置：$backup"
    return
  fi

  cat >&2 <<MSG

发现 $DEFAULT_ENABLED 里仍然配置了 $WEB_DOMAIN。
这会导致 Nginx 提示 conflicting server name。

如需脚本自动禁用该 default 入口，请重新执行：
  sudo AUTO_DISABLE_DEFAULT_WWW=1 $0

或者手动用 vim 移除 default 里的 $WEB_DOMAIN server 块。
MSG
}

show_conflicts() {
  log "检查 server_name 冲突"
  grep -RIn "server_name .*${WEB_DOMAIN//./\\.}" "$SITES_ENABLED" "$SITES_AVAILABLE" || true
}

reload_nginx() {
  if [[ "$CONFIG_CHANGED" != "1" ]]; then
    log "Nginx 配置未变更，跳过检查和重载"
    return
  fi
  log "检查 Nginx 配置"
  nginx -t
  log "重载 Nginx"
  systemctl reload nginx
}

verify() {
  log "验证同源 API"
  curl -fsS "https://$WEB_DOMAIN/api/health" || true
  printf '\n'
}

main() {
  require_root
  check_inputs
  log "检查 $WEB_DOMAIN 的 Web + /api 同源代理配置"
  write_config_if_changed
  enable_config
  maybe_disable_default_conflict
  show_conflicts
  reload_nginx
  verify
}

main "$@"
