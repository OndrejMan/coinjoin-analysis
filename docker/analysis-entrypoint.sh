#!/usr/bin/env bash
set -euo pipefail

cd /opt/coinjoin-analysis

show_help() {
  cat <<'EOF'
CoinJoin analysis container

Commands:
  help                         Show this help.
  analyze-emul [args...]       Run python -m cj_process.parse_cj_logs.
  analyze-client [args...]     Run python -m cj_process.ww2_analyze_client.

Any other command is executed as-is, for example:
  docker compose run --rm emulation-process python -m cj_process.parse_cj_logs --help
EOF
}

emulation_target_path() {
  local args=("$@")
  local index=0

  while [[ "${index}" -lt "${#args[@]}" ]]; do
    case "${args[$index]}" in
      --target-path|-tp)
        echo "${args[$((index + 1))]:-/runs/emulation/logs}"
        return
        ;;
      --target-path=*)
        echo "${args[$index]#--target-path=}"
        return
        ;;
      -tp=*)
        echo "${args[$index]#-tp=}"
        return
        ;;
    esac
    index=$((index + 1))
  done

  echo "/runs/emulation/logs"
}

validate_emulation_target() {
  local target_path="$1"

  if [[ ! -d "${target_path}" ]]; then
    cat >&2 <<EOF
EmuCoinJoin output path does not exist: ${target_path}

Create/copy your EmuCoinJoin results under the mounted runs directory first.
Default host path:
  ./runs/emulation/logs

Expected shape:
  ./runs/emulation/logs/<batch-or-run>/<experiment>/data/
EOF
    exit 2
  fi

  if [[ -z "$(find "${target_path}" -mindepth 2 -maxdepth 3 -type d -name data -print -quit)" ]]; then
    cat >&2 <<EOF
No EmuCoinJoin experiments found under: ${target_path}

Expected at least one experiment folder with a data/ subfolder, for example:
  ${target_path}/my-run/experiment-1/data/
EOF
    exit 2
  fi
}

command_name="${1:-help}"

case "${command_name}" in
  help|-h|--help)
    show_help
    ;;
  analyze-emul)
    shift
    validate_emulation_target "$(emulation_target_path "$@")"
    exec python -m cj_process.parse_cj_logs "$@"
    ;;
  analyze-client)
    shift
    exec python -m cj_process.ww2_analyze_client "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
