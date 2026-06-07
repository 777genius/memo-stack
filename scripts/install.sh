#!/usr/bin/env bash
set -euo pipefail

PREFIX="${MEMO_STACK_HOME:-${HOME}/.memo-stack}"
REPO_URL="${MEMO_STACK_INSTALL_REPO:-https://github.com/belief-ai/memo-stack.git}"
REF="${MEMO_STACK_INSTALL_REF:-main}"
NO_START=0
DRY_RUN=0
FORCE=0
RESET=0
RESET_DATA=0

usage() {
  cat <<'USAGE'
Memo Stack local installer.

Usage:
  scripts/install.sh [options]

Options:
  --dry-run             Print actions without writing files.
  --prefix PATH         Install home. Defaults to ~/.memo-stack.
  --repo URL_OR_PATH    Git repo URL or local path.
  --ref REF             Git ref to checkout. Defaults to main.
  --no-start            Install files only, do not start Docker stack.
  --force               Overwrite generated config files.
  --reset               Stop existing containers before install. Keeps data volumes.
  --reset-data          With --reset, remove compose volumes too.
  -h, --help            Show help.
USAGE
}

log() {
  printf '%s\n' "memo-stack install: $*" >&2
}

run() {
  if [ "${DRY_RUN}" = "1" ]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --dry-run)
        DRY_RUN=1
        ;;
      --prefix)
        shift
        PREFIX="${1:?--prefix requires a path}"
        ;;
      --repo)
        shift
        REPO_URL="${1:?--repo requires a URL or path}"
        ;;
      --ref)
        shift
        REF="${1:?--ref requires a git ref}"
        ;;
      --no-start)
        NO_START=1
        ;;
      --force)
        FORCE=1
        ;;
      --reset)
        RESET=1
        ;;
      --reset-data)
        RESET_DATA=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log "unknown argument: $1"
        usage >&2
        exit 2
        ;;
    esac
    shift
  done
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "required command missing: $1"
    exit 127
  fi
}

require_docker_compose() {
  if ! docker compose version >/dev/null 2>&1; then
    log "docker compose is unavailable"
    exit 127
  fi
}

prepare_dirs() {
  run mkdir -p "${PREFIX}/bin" "${PREFIX}/logs" "${PREFIX}/run"
}

clone_or_update_repo() {
  local src_dir="${PREFIX}/src"
  if [ ! -d "${src_dir}/.git" ]; then
    if [ -e "${src_dir}" ]; then
      log "${src_dir} exists but is not a git checkout"
      exit 1
    fi
    run git clone --branch "${REF}" "${REPO_URL}" "${src_dir}"
    return 0
  fi
  run git -C "${src_dir}" fetch --all --tags --prune
  run git -C "${src_dir}" checkout "${REF}"
  run git -C "${src_dir}" pull --ff-only || true
}

reset_runtime_if_requested() {
  if [ "${RESET}" != "1" ]; then
    return 0
  fi
  local src_dir="${PREFIX}/src"
  if [ ! -f "${src_dir}/docker-compose.yml" ]; then
    return 0
  fi
  if [ "${RESET_DATA}" = "1" ]; then
    run docker compose --project-directory "${src_dir}" --profile lite --profile full down -v
  else
    run docker compose --project-directory "${src_dir}" --profile lite --profile full down
  fi
}

ensure_config() {
  local src_dir="${PREFIX}/src"
  local config_path="${PREFIX}/config.toml"
  local env_path="${PREFIX}/.env"
  if [ "${FORCE}" = "1" ] || [ ! -f "${config_path}" ]; then
    if [ "${DRY_RUN}" = "1" ]; then
      log "would write ${config_path}"
    else
      cat >"${config_path}" <<EOF
[local]
home = "${PREFIX}"
repo_dir = "${src_dir}"
api_url = "http://127.0.0.1:7788"
default_space_slug = "default"
default_profile_external_ref = "default"

[runtime]
mode = "docker_compose"
profile = "lite"
compose_project_name = "memo_stack"

[mcp]
write_mode = "suggest"
delete_mode = "off"
ingest_mode = "small_docs"
EOF
    fi
  fi
  if [ "${FORCE}" = "1" ] || [ ! -f "${env_path}" ]; then
    if [ "${DRY_RUN}" = "1" ]; then
      log "would write ${env_path}"
    else
      local token
      token="$(python3 - <<'PY'
import secrets
print("mst_" + secrets.token_urlsafe(32))
PY
)"
      {
        printf 'MEMORY_SERVICE_TOKEN=%s\n' "${token}"
        printf 'MEMORY_POLICY_MODE=active_context\n'
        printf 'MEMORY_DEFAULT_SPACE_SLUG=default\n'
        printf 'MEMORY_DEFAULT_PROFILE_EXTERNAL_REF=default\n'
      } >"${env_path}"
      chmod 600 "${env_path}" || true
    fi
  fi
}

install_cli_shim() {
  local shim="${PREFIX}/bin/memo-stack"
  local src_dir="${PREFIX}/src"
  if [ "${DRY_RUN}" = "1" ]; then
    log "would write ${shim}"
    return 0
  fi
  cat >"${shim}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
repo_root="${src_dir}"
python_bin="\${repo_root}/.venv/bin/python"
if [ ! -x "\${python_bin}" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python_bin="\$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    python_bin="\$(command -v python)"
  else
    printf '%s\n' "memo-stack: python not found" >&2
    exit 127
  fi
fi
export MEMO_STACK_HOME="${PREFIX}"
export MEMO_STACK_REPO_ROOT="\${repo_root}"
memo_stack_pythonpath="\${repo_root}/packages/memo_stack_core:\${repo_root}/packages/memo_stack_server:\${repo_root}/packages/memo_stack_adapters:\${repo_root}/packages/memo_stack_sdk:\${repo_root}/packages/memo_stack_obsidian:\${repo_root}/packages/memo_stack_mcp:\${repo_root}/packages/memo_stack_cli"
if [ -n "\${PYTHONPATH:-}" ]; then
  export PYTHONPATH="\${memo_stack_pythonpath}:\${PYTHONPATH}"
else
  export PYTHONPATH="\${memo_stack_pythonpath}"
fi
exec "\${python_bin}" -m memo_stack_cli "\$@"
EOF
  chmod +x "${shim}"
}

start_if_requested() {
  if [ "${NO_START}" = "1" ]; then
    return 0
  fi
  run "${PREFIX}/bin/memo-stack" up --lite
  run "${PREFIX}/bin/memo-stack" doctor
}

print_next_steps() {
  cat <<EOF
Memo Stack installed.

Next:
  export PATH="${PREFIX}/bin:\$PATH"
  memo-stack status
  memo-stack mcp-config --agent codex
  memo-stack digest "current architecture decisions" --space default --profile default
EOF
}

main() {
  parse_args "$@"
  require_command bash
  require_command git
  require_command docker
  require_command python3
  require_docker_compose
  prepare_dirs
  clone_or_update_repo
  reset_runtime_if_requested
  ensure_config
  install_cli_shim
  start_if_requested
  print_next_steps
}

main "$@"
