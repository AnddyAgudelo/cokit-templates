#!/bin/bash
set -e

cd "$(dirname "$0")/../agent"

source .venv/bin/activate
exec npx @langchain/langgraph-cli dev --port 8124 --no-browser
