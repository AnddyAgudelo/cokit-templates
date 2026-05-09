#!/bin/bash
set -e

cd "$(dirname "$0")/../agent"

if ! command -v uv &> /dev/null; then
  echo "uv not found. Install from https://docs.astral.sh/uv/"
  exit 1
fi

uv venv --python 3.12
uv pip install -e ".[dev]"

echo "Agent setup complete. Run from repo root: npm run dev"
