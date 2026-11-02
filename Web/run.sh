#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python Web/run.py
else
    python3 Web/run.py
fi
