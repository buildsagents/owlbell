#!/usr/bin/env sh
# Editable install from the canonical project root (see ../pyproject.toml).
set -eu
cd "$(dirname "$0")/.."
python -m pip install -e ".[dev]" --no-deps --ignore-requires-python "$@"