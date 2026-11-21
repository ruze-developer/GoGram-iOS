#!/usr/bin/env bash
set -Eeuo pipefail
WEB_SOURCE=/opt/owpengram-web-client
TARGET_IP=48.102.206.129
MTPROTO_PORT=2398
NGINX_SITE=/etc/nginx/sites-available/owpengram-web
SERVER_SOURCE="$(printenv OWPENGRAM_SERVER_DIR || true)"
if [[ "$EUID" -ne 0 ]]; then echo 'Run with sudo' >&2; exit 1; fi
for command in git node pnpm nginx; do
  command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
if [[ -z "$SERVER_SOURCE" ]]; then
  for candidate in /root/owpengram-server /opt/owpengram-server /srv/owpengram-server; do
    if [[ -f "$candidate/internal/webclient/webclient.go" ]]; then SERVER_SOURCE="$candidate"; break; fi
  done
fi
if [[ ! -f "$SERVER_SOURCE/internal/webclient/webclient.go" ]]; then
  echo 'Cannot find server checkout: export OWPENGRAM_SERVER_DIR=/path/to/owpengram-server' >&2
  exit 1
fi
if [[ ! -d "$WEB_SOURCE/.git" ]]; then
  git clone --depth 1 https://github.com/owpengram/owpengram-web-client.git "$WEB_SOURCE"
fi
cd "$WEB_SOURCE"
node scripts/owpengram-web.mjs embed --server-dir "$SERVER_SOURCE"
if [[ ! -f "$SERVER_SOURCE/internal/webclient/dist/index.html" ]]; then
  echo 'Web build missing index.html' >&2; exit 1
fi
if [[ -e "$NGINX_SITE" ]]; then
  echo "Refusing to overwrite existing $NGINX_SITE" >&2
  exit 1
fi
if nginx -T 2>/dev/null | grep -E '^[[:space:]]*server_name[[:space:]]+' | grep -q '48\.102\.206\.129'; then
  echo 'nginx already has a vhost for 48.102.206.129; refusing to change routes' >&2
  exit 1
fi
cat > "$NGINX_SITE" <<'NGINX'
server {
    listen 80;
    server_name 48.102.206.129;
    client_max_body_size 50m;
    location / {
        proxy_pass http://127.0.0.1:2398;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_buffering off;
    }
}
NGINX
ln -s "$NGINX_SITE" /etc/nginx/sites-enabled/owpengram-web
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/owpengram-web "$NGINX_SITE"
  echo 'Invalid nginx config, reverted new site' >&2
  exit 1
fi
echo 'Frontend embedded into source and nginx config validated.'
echo 'Rebuild/restart the OwpenGram server using its EXISTING launcher, then: systemctl reload nginx'
echo 'TELESRV_WEB_CLIENT_ENABLE and TELESRV_WEBSOCKET_ENABLE must be true.'
echo 'Allow http://48.102.206.129 WebSocket origin if necessary.'
echo 'Use HTTPS/WSS for secure production logins.'
