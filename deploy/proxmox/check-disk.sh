#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
threshold=${SECURO_DISK_WARNING_PERCENT:-80}
used=$(df -P "$repo_dir" | awk 'NR == 2 { gsub(/%/, "", $5); print $5 }')

echo "Securo filesystem usage: ${used}% (warning threshold: ${threshold}%)"
docker system df

if [ "$used" -ge "$threshold" ]; then
  echo "WARNING: Securo filesystem usage reached ${used}%." >&2
  echo "Review old images with: docker image ls" >&2
  echo "Remove only images you have confirmed are not rollback targets." >&2
  exit 1
fi
