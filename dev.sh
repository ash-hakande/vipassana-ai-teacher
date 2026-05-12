#!/usr/bin/env bash
set -e

# Use .venv inside the project directory (works on any machine)
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

usage() {
  echo "Usage: ./dev.sh <command>"
  echo ""
  echo "  install   Create .venv and install dependencies"
  echo "  ingest    Load documents into the vector store (run before 'start')"
  echo "  start     Start the dev server at http://localhost:8085"
  echo ""
}

case "$1" in
  install)
    cd "$DIR"
    # Ensure build tools and python3-venv are available (required on Ubuntu servers)
    if ! command -v g++ &>/dev/null; then
      echo "Installing build-essential..."
      apt install -y build-essential
    fi
    if ! python3 -m venv --help &>/dev/null; then
      echo "Installing python3-venv..."
      apt install -y python3-venv python3-pip
    fi
    python3 -m venv .venv
    $VENV/bin/pip install --upgrade pip -q
    $VENV/bin/pip install "numpy<2.0" onnxruntime==1.23.2 -q
    $VENV/bin/pip install -r requirements.txt -q
    echo "Dependencies installed in $VENV"
    ;;
  ingest)
    cd "$DIR"
    $PYTHON -m app.ingest
    ;;
  start)
    cd "$DIR"
    PORT=$(grep -E '^PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    PORT=${PORT:-8085}
    $UVICORN app.main:app --host 0.0.0.0 --port "$PORT" --reload
    ;;
  *)
    usage
    ;;
esac
