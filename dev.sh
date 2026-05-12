#!/usr/bin/env bash
set -e

VENV="/home/aishwarya/.cache/pypoetry/virtualenvs/vipassana-ai-teacher-YAdGNT4d-py3.10"
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

usage() {
  echo "Usage: ./dev.sh <command>"
  echo ""
  echo "  install   Install dependencies"
  echo "  ingest    Load documents into the vector store (run before 'start')"
  echo "  start     Start the dev server at http://localhost:8085"
  echo ""
}

case "$1" in
  install)
    pip install "numpy<2.0" onnxruntime==1.23.2 -q
    pip install -r requirements.txt -q
    echo "Dependencies installed."
    ;;
  ingest)
    cd "$(dirname "$0")"
    $PYTHON -m app.ingest
    ;;
  start)
    cd "$(dirname "$0")"
    $UVICORN app.main:app --host 0.0.0.0 --port 8085 --reload
    ;;
  *)
    usage
    ;;
esac
