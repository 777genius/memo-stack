#!/bin/sh
set -eu

asset_dir="${MEMORY_ASSET_STORAGE_DIR:-/var/lib/infinity-context/assets}"

mkdir -p "$asset_dir"
chown memo:memo /var/lib/infinity-context "$asset_dir" /home/memo

exec gosu memo "$@"
