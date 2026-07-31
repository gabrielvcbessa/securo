#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tag=${1:-}
commit=${tag#sha-}

case "$commit" in
  *[!0-9a-f]*)
    echo "Usage: $0 sha-<full-git-commit>" >&2
    echo "Mutable tags such as latest are intentionally rejected." >&2
    exit 2
    ;;
esac

if [ "$tag" = "$commit" ] || [ "${#commit}" -ne 40 ]; then
  echo "Usage: $0 sha-<full-git-commit>" >&2
  echo "The image tag must contain exactly 40 lowercase hexadecimal characters." >&2
  exit 2
fi

if [ ! -f "$repo_dir/.env" ]; then
  echo "Missing $repo_dir/.env; copy deploy/proxmox/.env.example first." >&2
  exit 2
fi

cd "$repo_dir"
if [ -f .deploy-tag ]; then
  cp .deploy-tag .previous-deploy-tag
fi

umask 077
tag_file=$(mktemp "$repo_dir/.deploy-tag.XXXXXX")
printf 'SECURO_IMAGE_TAG=%s\n' "$tag" > "$tag_file"
mv "$tag_file" .deploy-tag

compose_files="-f docker-compose.prod.yml -f deploy/proxmox/compose.compact.yml -f deploy/proxmox/compose.caddy.yml"

# shellcheck disable=SC2086
docker compose --env-file .env --env-file .deploy-tag $compose_files pull
# shellcheck disable=SC2086
docker compose --env-file .env --env-file .deploy-tag $compose_files up -d --remove-orphans
# shellcheck disable=SC2086
docker compose --env-file .env --env-file .deploy-tag $compose_files ps

echo "Deployed Securo image tag: $tag"
echo "Previous tag, when available: $repo_dir/.previous-deploy-tag"
