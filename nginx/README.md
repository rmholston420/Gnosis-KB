# Gnosis KB — Nginx Reverse Proxy

Nginx is the **single public entry point** for the Gnosis KB Docker stack.
It terminates TLS, applies security headers, rate-limits the API, and
proxies traffic to the `api` and `ui` containers on the internal Docker
network — neither of those services exposes a host port in production.

## File Map

| File | Purpose |
|------|---------|
| `nginx.conf` | Production: HTTP→HTTPS redirect + TLS termination + security headers |
| `nginx.dev.conf` | Local dev: plain HTTP on port `8080`, no TLS |
| `certbot-renew.service` | systemd oneshot unit — runs `certbot renew` + nginx reload |
| `certbot-renew.timer` | systemd timer — fires at 03:15 and 15:15 daily |
| `certs/` | Mount point for TLS cert files (git-ignored) |

## Request Flow

```
Browser
  │
  ├─ HTTP  :80   ──→  redirect to HTTPS (ACME challenge exempt)
  └─ HTTPS :443  ──┐
                   │
              [Nginx container]
                   ├── /api/*            ──→  api:8010  (FastAPI / uvicorn)
                   ├── /health           ──→  api:8010  (liveness probe)
                   └── /*                ──→  ui:3010   (React SPA)
```

For local dev, Compose picks up `docker-compose.override.yml` automatically,
which swaps `nginx.conf` → `nginx.dev.conf` and exposes `api:8010` + `ui:3010`
directly so you can develop without TLS.

## Quick Start — Local Dev (no TLS)

```bash
# docker-compose.override.yml is picked up automatically
docker compose up -d
open http://localhost:8080
```

Direct access (bypassing Nginx) is also available at:
- API: http://localhost:8010/docs
- UI:  http://localhost:3010

## Production Deployment (Let's Encrypt)

The `deploy.sh` script in the repo root handles the full bootstrap:

```bash
chmod +x deploy.sh
DOMAIN=kb.yourdomain.com EMAIL=you@example.com ./deploy.sh
```

What it does:
1. Installs `certbot` if missing (via snap)
2. Creates `.env` from `.env.example` if not present and exits for you to edit
3. Validates `SECRET_KEY` is not the placeholder
4. Runs `certbot certonly --standalone` to obtain the initial certificate
5. Patches `.env` with `TLS_CERT_DIR` and `nginx.conf` with `server_name`
6. Builds and starts the Docker stack
7. Runs `alembic upgrade head`
8. Installs the `certbot-renew` systemd timer for automatic renewal

### Manual TLS setup (without deploy.sh)

```bash
# 1. Get a cert
sudo certbot certonly --standalone -d kb.yourdomain.com

# 2. Set cert path
echo 'TLS_CERT_DIR=/etc/letsencrypt/live/kb.yourdomain.com' >> .env

# 3. Set server_name in nginx/nginx.conf
sed -i 's/server_name _;/server_name kb.yourdomain.com;/g' nginx/nginx.conf

# 4. Start stack (delete docker-compose.override.yml first)
docker compose up -d

# 5. Run migrations
docker compose exec api alembic upgrade head

# 6. Install renewal timer
sudo cp nginx/certbot-renew.{service,timer} /etc/systemd/system/
sudo systemctl enable --now certbot-renew.timer
```

### Enable HSTS (after verifying TLS works)

Uncomment in `nginx/nginx.conf`:
```nginx
add_header Strict-Transport-Security "max-age=63072000" always;
```

## Rate Limits

| Zone | Applies to | Rate | Burst |
|------|-----------|------|-------|
| `api_limit` | All `/api/` routes | 60 req/min | 20 |
| `search_limit` | `/api/search/semantic` | 20 req/min | 5 |

Adjust `nginx.conf` `limit_req_zone` directives to tune for your usage.

## Security Headers (all responses)

| Header | Value |
|--------|-------|
| `X-Frame-Options` | `SAMEORIGIN` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'self'` (tighten as needed) |
| `Server` header | Suppressed (`server_tokens off`) |

## Static Asset Caching

Assets matching `*.js`, `*.css`, `*.woff2`, `*.png`, etc. get:
```
Cache-Control: public, immutable
Expires: 1 year
```
Vite hashes filenames on every build so this is safe and eliminates
repeat downloads for returning users.
