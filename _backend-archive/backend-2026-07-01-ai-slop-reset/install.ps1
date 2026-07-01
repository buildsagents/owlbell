# Editable install from the canonical project root (see ../pyproject.toml).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
python -m pip install -e ".[dev]" --no-deps --ignore-requires-python @args