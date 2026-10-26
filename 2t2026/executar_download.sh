#!/usr/bin/env bash
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$RAIZ/scripts/baixar_dados.py" --config "$RAIZ/config.json" "$@"
