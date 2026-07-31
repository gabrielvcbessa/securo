#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
previous_file="$repo_dir/.previous-deploy-tag"

if [ ! -f "$previous_file" ]; then
  echo "No previous deployment tag is recorded." >&2
  exit 2
fi

previous_tag=$(sed -n 's/^SECURO_IMAGE_TAG=//p' "$previous_file")
if [ -z "$previous_tag" ]; then
  echo "The previous deployment tag file is invalid." >&2
  exit 2
fi

exec "$repo_dir/deploy/proxmox/deploy.sh" "$previous_tag"
