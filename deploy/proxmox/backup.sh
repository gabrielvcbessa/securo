#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "${script_dir}/../.." && pwd)
env_file=${SECURO_ENV_FILE:-"${repo_dir}/.env"}

if [ ! -r "${env_file}" ]; then
  echo "Securo environment file is not readable: ${env_file}" >&2
  exit 1
fi

set -a
# The deployment .env is operator-controlled and intentionally loaded here.
# shellcheck disable=SC1090
. "${env_file}"
set +a

backup_dir=${SECURO_BACKUP_DIR:-/mnt/securo-backups}
postgres_user=${POSTGRES_USER:-postgres}
postgres_db=${POSTGRES_DB:-securo}

if ! mountpoint -q "${backup_dir}"; then
  echo "Backup target is not a mounted filesystem: ${backup_dir}" >&2
  echo "Refusing to write to the VM disk when the NAS is unavailable." >&2
  exit 1
fi

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
temporary_dir="${backup_dir}/.securo-${timestamp}.tmp"
final_dir="${backup_dir}/securo-${timestamp}"

cleanup() {
  if [ -d "${temporary_dir}" ]; then
    rm -rf -- "${temporary_dir}"
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "${temporary_dir}"

docker compose \
  --env-file "${env_file}" \
  -f "${repo_dir}/docker-compose.prod.yml" \
  exec -T db \
  pg_dump --username "${postgres_user}" --dbname "${postgres_db}" --format=custom \
  > "${temporary_dir}/database.dump"

docker compose \
  --env-file "${env_file}" \
  -f "${repo_dir}/docker-compose.prod.yml" \
  exec -T backend \
  python -c 'import sys, tarfile
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    for name in ("attachments", "agent_knowledge"):
        archive.add(f"/app/data/{name}", arcname=name)' \
  > "${temporary_dir}/files.tar.gz"

(
  cd "${temporary_dir}"
  sha256sum database.dump files.tar.gz > SHA256SUMS
)

mv "${temporary_dir}" "${final_dir}"
trap - EXIT INT TERM
echo "Securo backup completed: ${final_dir}"
