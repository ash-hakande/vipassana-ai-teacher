#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

usage() {
  echo "Usage: ./backend/dev.sh <command>"
  echo ""
  echo "  install   Create .venv and install dependencies"
  echo "  ingest    Load documents into the vector store"
  echo "  start     Start with auto-reload"
  echo "  serve     Start without auto-reload"
  echo ""
}

case "$1" in
  install)
    cd "$DIR"
    python3 -m venv .venv
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -r requirements.txt -q
    echo "Dependencies installed in $VENV"
    ;;
  ingest)
    cd "$DIR"
    "$PYTHON" -m app.ingest
    ;;
  start)
    cd "$DIR"
    PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    PORT=${PORT:-9090}
    "$UVICORN" app.main:app --host 0.0.0.0 --port "$PORT" --reload
    ;;
  serve)
    cd "$DIR"
    PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    PORT=${PORT:-9090}
    "$UVICORN" app.main:app --host 0.0.0.0 --port "$PORT"
    ;;
  *)
    usage
    ;;
esac
