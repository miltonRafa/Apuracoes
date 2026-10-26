#!/usr/bin/env bash
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --disable-pip-version-check -r 04_bi/requirements-notebook.txt
.venv/bin/python 04_bi/scripts/prepare_sources.py --ano 2022 --turno 2
.venv/bin/python 04_bi/scripts/build_bi.py
.venv/bin/python 04_bi/scripts/validate_bi.py
.venv/bin/python 04_bi/scripts/create_analysis_notebook.py
