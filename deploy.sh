#!/usr/bin/env bash
# =============================================================================
# Gnosis KB — Production deployment bootstrap
# =============================================================================
# Run once on a fresh Ubuntu/Debian host that already has:
#   - Docker + Docker Compose v2
#   - A DNS A-record pointing DOMAIN to this server's IP
#
# Usage:
#   chmod +x deploy.sh
#   DOMAIN=kb.yourdomain.com EMAIL=you@example.com ./deploy.sh
# =============================================================================
set -euo pipefail

# ---- Config (override via env or edit here) ---------------------------------
DOMAIN="${DOMAIN:?Set DOMAIN=kb.yourdomain.com}"
EMAIL="${EMAIL:?Set EMAIL=you@example.com}"
COMPOSE_FILE="$(dirname "$0")/docker-compose.yml"
NGINX_CONF="$(dirname "$0")/nginx/nginx.conf"
ENV_FILE="$(dirname "$0")/.env"

info()  { echo "\e[32m[INFO]\e[0m  $*"; }
warn()  { echo "\e[33m[WARN]\e[0m  $*"; }
error() { echo "\e[31m[ERROR]\e[0m $*" >&2; exit 1; }

# ---- 1. Check prerequisites -------------------------------------------------
info "Checking prerequisites…"
command -v docker  >/dev/null 2>&1 || error "docker not found. Install Docker first."
command -v certbot >/dev/null 2>&1 || {
    warn "certbot not found — installing via snap…"
    sudo snap install --classic certbot
    sudo ln -sf /snap/bin/certbot /usr/bin/certbot
}

# ---- 2. Create .env if it doesn't exist ------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    info "Creating .env from .env.example…"
    cp "$(dirname "$0")/.env.example" "$ENV_FILE"
    warn "Edit .env before continuing — especially SECRET_KEY, POSTGRES_PASSWORD."
    warn "Re-run this script after editing .env."
    exit 0
fi

# Ensure SECRET_KEY is not the placeholder
if grep -q 'changeme-replace-in-production' "$ENV_FILE"; then
    error ".env still has the default SECRET_KEY. Set a real secret first."
fi

# ---- 3. Obtain TLS certificate (standalone — Nginx not yet running) ---------
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [[ ! -f "${CERT_DIR}/fullchain.pem" ]]; then
    info "Requesting Let's Encrypt certificate for ${DOMAIN}…"
    sudo certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "${EMAIL}" \
        -d "${DOMAIN}" \
        -d "www.${DOMAIN}" || warn "www.${DOMAIN} may not have a DNS record — retrying without www…" && \
    sudo certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "${EMAIL}" \
        -d "${DOMAIN}"
else
    info "Certificate already exists at ${CERT_DIR} — skipping issuance."
fi

# ---- 4. Patch .env with TLS cert dir ---------------------------------------
if ! grep -q 'TLS_CERT_DIR' "$ENV_FILE"; then
    echo "" >> "$ENV_FILE"
    echo "# TLS" >> "$ENV_FILE"
    echo "TLS_CERT_DIR=${CERT_DIR}" >> "$ENV_FILE"
    info "Added TLS_CERT_DIR=${CERT_DIR} to .env"
else
    sed -i "s|TLS_CERT_DIR=.*|TLS_CERT_DIR=${CERT_DIR}|" "$ENV_FILE"
    info "Updated TLS_CERT_DIR in .env"
fi

# ---- 5. Patch nginx.conf server_name ---------------------------------------
info "Setting server_name to ${DOMAIN} in nginx.conf…"
sed -i "s/server_name _;/server_name ${DOMAIN} www.${DOMAIN};/g" "$NGINX_CONF"

# ---- 6. Build + start stack -------------------------------------------------
info "Building and starting Docker stack…"
docker compose -f "$COMPOSE_FILE" pull postgres qdrant nginx
docker compose -f "$COMPOSE_FILE" build api ui
docker compose -f "$COMPOSE_FILE" up -d

# ---- 7. Run Alembic migrations ----------------------------------------------
info "Running database migrations…"
sleep 5  # wait for postgres to be healthy
docker compose -f "$COMPOSE_FILE" exec api alembic upgrade head

# ---- 8. Install systemd cert-renewal timer ----------------------------------
info "Installing certbot renewal systemd timer…"
sudo cp "$(dirname "$0")/nginx/certbot-renew.service" /etc/systemd/system/
sudo cp "$(dirname "$0")/nginx/certbot-renew.timer"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now certbot-renew.timer
info "Renewal timer active: $(systemctl status certbot-renew.timer --no-pager | grep Active)"

# ---- Done -------------------------------------------------------------------
info "✅  Gnosis KB is live at https://${DOMAIN}"
info "    API docs: https://${DOMAIN}/docs"
info "    Health:   https://${DOMAIN}/health"
