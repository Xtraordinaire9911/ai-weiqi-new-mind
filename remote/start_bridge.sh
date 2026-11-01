#!/usr/bin/env bash
# start_bridge.sh -- starts remote/katago_bridge.py with the KataGo binary and network found on this machine (Linux and macOS).
# It only looks at a few usual places on THIS computer and starts the bridge on 127.0.0.1. Nothing is downloaded, installed or sent anywhere.
#
#   remote/start_bridge.sh                      find KataGo and a network, start the bridge on port 8787
#   remote/start_bridge.sh --print-setup        print what you must provide, then exit
#   remote/start_bridge.sh --katago PATH --model PATH [--config PATH] [--port N]
#   remote/start_bridge.sh --fake               no KataGo at all, simulated data (to try the page)
#   remote/start_bridge.sh -- --allow-origin https://example.org      everything after "--" goes to katago_bridge.py
#
# Environment: KATAGO_BIN, KATAGO_MODEL, KATAGO_CONFIG, KATAGO_MODELS_DIR, KATAGO_BRIDGE_TOKEN (a random token is printed once when unset).
set -eu
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin="${KATAGO_BIN:-}"; model="${KATAGO_MODEL:-}"; config="${KATAGO_CONFIG:-}"; port=8787; fake=0; setup=0
extra=()
while [ $# -gt 0 ]; do
  case "$1" in
    --print-setup) setup=1 ;;
    --katago) bin="$2"; shift ;;
    --model) model="$2"; shift ;;
    --config) config="$2"; shift ;;
    --port) port="$2"; shift ;;
    --fake) fake=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    --) shift; extra=("$@"); break ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done

py=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then py="$c"; break; fi
done
[ -n "$py" ] || { echo "Python 3.8 or newer is needed (the bridge uses only its standard library)." >&2; exit 2; }
if [ "$setup" = 1 ]; then exec "$py" "$here/katago_bridge.py" --print-setup; fi
if [ "$fake" = 1 ]; then exec "$py" "$here/katago_bridge.py" --fake --port "$port" ${extra[@]+"${extra[@]}"}; fi

# ---- find the KataGo binary
if [ -z "$bin" ]; then
  for c in "$(command -v katago 2>/dev/null || true)" "$HOME/katago/katago" "$HOME/.katago/katago" /opt/katago/katago /usr/local/bin/katago \
           /opt/homebrew/bin/katago /usr/games/katago "$HOME"/Downloads/katago*/katago "$HOME"/katago*/katago; do
    if [ -n "$c" ] && [ -f "$c" ] && [ -x "$c" ]; then bin="$c"; break; fi
  done
fi
# ---- find a network (newest .bin.gz in the usual places)
if [ -z "$model" ]; then
  dirs=()
  [ -n "${KATAGO_MODELS_DIR:-}" ] && dirs+=("$KATAGO_MODELS_DIR")
  [ -n "$bin" ] && dirs+=("$(dirname "$bin")" "$(dirname "$bin")/models")
  dirs+=("$HOME/katago" "$HOME/katago/models" "$HOME/.katago" "$HOME/.katago/models" /opt/katago /opt/katago/models "$HOME/Downloads")
  for d in "${dirs[@]}"; do
    [ -d "$d" ] || continue
    f="$(ls -t "$d"/*.bin.gz 2>/dev/null | head -n 1 || true)"
    if [ -n "$f" ]; then model="$f"; break; fi
  done
fi
miss=0
if [ -z "$bin" ] || [ ! -x "$bin" ]; then echo "KataGo executable not found. Give it with --katago PATH or KATAGO_BIN." >&2; miss=1; fi
if [ -z "$model" ] || [ ! -f "$model" ]; then echo "Network file (.bin.gz) not found. Give it with --model PATH or KATAGO_MODEL." >&2; miss=1; fi
if [ "$miss" = 1 ]; then echo >&2; "$py" "$here/katago_bridge.py" --print-setup >&2; exit 2; fi

echo "KataGo : $bin"
echo "Network: $model"
args=(--katago "$bin" --model "$model" --models-dir "$(dirname "$model")" --port "$port")
[ -n "$config" ] && { echo "Config : $config"; args+=(--config "$config"); }
exec "$py" "$here/katago_bridge.py" "${args[@]}" ${extra[@]+"${extra[@]}"}
