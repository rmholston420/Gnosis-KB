#!/usr/bin/env bash
# Gnosis PostgreSQL backup script
# Runs inside a dedicated `backup` Docker service (see docker-compose.yml).
# Dumps are written to BACKUP_DIR (mounted from the host) as compressed .sql.gz
# files named by timestamp.  Files older than RETAIN_DAYS are pruned.
#
# Environment variables (all have defaults):
#   POSTGRES_HOST     — default: postgres
#   POSTGRES_PORT     — default: 5432
#   POSTGRES_USER     — default: gnosis
#   POSTGRES_PASSWORD — required (passed via Docker secret / env)
#   POSTGRES_DB       — default: gnosis
#   BACKUP_DIR        — default: /backups
#   RETAIN_DAYS       — default: 7

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-gnosis}"
POSTGRES_DB="${POSTGRES_DB:-gnosis}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT="${BACKUP_DIR}/gnosis_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting backup → ${OUTPUT}"

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-owner \
    --no-acl \
    | gzip > "${OUTPUT}"

echo "[$(date -Iseconds)] Backup complete: ${OUTPUT} ($(du -sh "${OUTPUT}" | cut -f1))"

# Prune backups older than RETAIN_DAYS
echo "[$(date -Iseconds)] Pruning backups older than ${RETAIN_DAYS} days..."
find "${BACKUP_DIR}" -name 'gnosis_*.sql.gz' -mtime +"${RETAIN_DAYS}" -delete
RETAINED=$(find "${BACKUP_DIR}" -name 'gnosis_*.sql.gz' | wc -l)
echo "[$(date -Iseconds)] Pruning done. ${RETAINED} backup(s) retained."
