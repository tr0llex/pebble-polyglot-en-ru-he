#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${FONT_PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    echo "Install the font environment as described in RUSSIAN.md" >&2
    exit 1
fi
exec "$PYTHON" "$ROOT/tools/l10n/buildfonts.py" "$@"
