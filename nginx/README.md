# Gnosis KB — Nginx Reverse Proxy

This directory contains Nginx configuration for the Gnosis KB production
deployment. Nginx is the single public entry point; it terminates TLS and
routes traffic to the `api` and `ui` Docker services internally.

## Files

| File | Purpose |
|------|---------|
| `nginx.conf` | Production config: HTTP→HTTPS redirect + TLS termination |
| `nginx.dev.conf` | Local dev config: plain HTTP on port `8080`, no TLS |
| `certs/` | Mount point for TLS certificate files (git-ignored) |

## Quick Start — Local Dev (no TLS)

1. Edit `docker-compose.yml` and change the nginx volume mount to use
   `nginx.dev.conf`:
   ```yaml
   - ./nginx/nginx.dev.conf:/etc/nginx/nginx.conf:ro
   ```
2. Comment out the two TLS cert volume lines.
3. Start the stack:
   ```bash
   docker compose up -d
   ```
4. Open `http://localhost:8080`.

The `api` and `ui` ports (`8010`, `3010`) are **not** exposed to the host
in production — all traffic routes through Nginx on port 80/443. For
direct backend access during development, uncomment the `ports:` sections
in `docker-compose.yml`.

## Production Deployment (TLS with Let's Encrypt)

### 1. Obtain a certificate

On the host machine (replace `yourdomain.com`):

```bash
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

### 2. Set the cert directory in your `.env`

```ini
TLS_CERT_DIR=/etc/letsencrypt/live/yourdomain.com
```

The `docker-compose.yml` uses `${TLS_CERT_DIR:-./nginx/certs}` so it
falls back to a local `./nginx/certs/` directory if the variable is unset.

### 3. Set your `server_name`

In `nginx/nginx.conf`, replace `server_name _;` with your domain:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

### 4. Enable HSTS (after verifying TLS works)

Uncomment this line in `nginx.conf`:

```nginx
add_header Strict-Transport-Security "max-age=63072000" always;
```

### 5. Auto-renewal

Certbot renews via a shared `certbot_webroot` Docker volume that maps
to `/.well-known/acme-challenge/` in the Nginx config. Add a cron job or
systemd timer on the host:

```bash
0 3 * * * certbot renew --quiet && docker compose -f /path/to/docker-compose.yml exec nginx nginx -s reload
```

## Request Flow

```
Browser
  │
  ├─ HTTPS :443  ─┐
  └─ HTTP  :80  ─┘
               │
          [Nginx container]
               ├── /api/*   ─────→ api:8010  (FastAPI / uvicorn)
               ├── /health  ─────→ api:8010  (liveness)
               └── /*       ─────→ ui:3010   (React SPA / nginx-alpine)
```

## Rate Limits

| Zone | Applies to | Limit |
|------|-----------|-------|
| `api_limit` | All `/api/` routes | 60 req/min, burst 20 |
| `search_limit` | `/api/search/semantic` | 20 req/min, burst 5 |

## Security Headers

Every response from Nginx includes:

- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` (tighten in production as needed)
- `Server: nginx` suppressed (`server_tokens off`)
