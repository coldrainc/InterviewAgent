#!/usr/bin/env bash
set -euo pipefail

NGINX_CONF_DIR="${NGINX_CONF_DIR:-/etc/nginx}"
NGINX_SECURITY_ZONES="${NGINX_SECURITY_ZONES:-$NGINX_CONF_DIR/conf.d/aivago-security-zones.conf}"
NGINX_SECURITY_SNIPPET="${NGINX_SECURITY_SNIPPET:-$NGINX_CONF_DIR/snippets/aivago-security.conf}"
FAIL2BAN_FILTER="${FAIL2BAN_FILTER:-/etc/fail2ban/filter.d/aivago-nginx.conf}"
FAIL2BAN_JAIL="${FAIL2BAN_JAIL:-/etc/fail2ban/jail.d/aivago.conf}"
INSTALL_PACKAGES="${INSTALL_PACKAGES:-1}"

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

write_if_changed() {
  local target="$1"
  local tmp
  tmp="$(mktemp)"
  cat > "$tmp"
  if [[ -f "$target" ]] && cmp -s "$tmp" "$target"; then
    rm -f "$tmp"
    echo "$target 未变更，跳过写入。"
    return
  fi
  mkdir -p "$(dirname "$target")"
  mv "$tmp" "$target"
  chmod 644 "$target"
  echo "已写入：$target"
}

install_fail2ban_if_needed() {
  if command -v fail2ban-client >/dev/null 2>&1; then
    return
  fi
  if [[ "$INSTALL_PACKAGES" != "1" ]]; then
    echo "未检测到 fail2ban，请手动安装：sudo apt install fail2ban"
    return
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "未检测到 apt-get，请按系统发行版手动安装 fail2ban。"
    return
  fi
  log "安装 fail2ban"
  apt-get update
  apt-get install -y fail2ban
}

write_nginx_security() {
  log "写入 Nginx WAF 与限流配置"
  write_if_changed "$NGINX_SECURITY_ZONES" <<'NGINX'
limit_req_zone $binary_remote_addr zone=aivago_api:10m rate=120r/m;
limit_conn_zone $binary_remote_addr zone=aivago_conn:10m;
NGINX

  write_if_changed "$NGINX_SECURITY_SNIPPET" <<'NGINX'
limit_req zone=aivago_api burst=80 nodelay;
limit_conn aivago_conn 30;

client_body_timeout 15s;
client_header_timeout 15s;
keepalive_timeout 65s;
send_timeout 30s;

if ($request_method !~ ^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)$) {
    return 405;
}

if ($request_uri ~* "(\.env|\.git|wp-admin|phpmyadmin|/etc/passwd|/proc/self|base64_decode|/bin/sh|cmd\.exe)") {
    return 403;
}

if ($query_string ~* "(union.*select|select.*from|information_schema|sleep\(|benchmark\(|<script|javascript:)") {
    return 403;
}

location ~ /\.(?!well-known) {
    deny all;
}
NGINX
}

write_fail2ban() {
  log "写入 fail2ban 规则"
  write_if_changed "$FAIL2BAN_FILTER" <<'FAIL2BAN'
[Definition]
failregex = ^<HOST> - .* "(GET|POST|HEAD) .*(\.env|\.git|wp-admin|phpmyadmin|/etc/passwd|/proc/self|base64_decode|/bin/sh|cmd\.exe|union.*select|<script).*" (403|404|444)
            ^<HOST> - .* "(POST|GET) /api/auth/(login|register|refresh).*" (401|429)
ignoreregex =
FAIL2BAN

  write_if_changed "$FAIL2BAN_JAIL" <<'FAIL2BAN'
[aivago-nginx-waf]
enabled = true
filter = aivago-nginx
logpath = /var/log/nginx/access.log
findtime = 600
maxretry = 8
bantime = 3600
banaction = ufw
port = http,https
protocol = tcp
FAIL2BAN
}

reload_services() {
  log "检查并重载 Nginx"
  nginx -t
  systemctl reload nginx

  if command -v fail2ban-client >/dev/null 2>&1; then
    log "重启 fail2ban"
    systemctl enable --now fail2ban
    systemctl restart fail2ban
    fail2ban-client status aivago-nginx-waf || true
  fi
}

main() {
  require_root
  install_fail2ban_if_needed
  write_nginx_security
  write_fail2ban
  reload_services
}

main "$@"
