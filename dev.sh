#!/usr/bin/env bash
set -e

COMPOSE_LOCAL="docker-compose.local.yml"
COMPOSE_PROD="docker-compose.yml"
LOCAL_CONTAINER="vipassana-ai-teacher-backend-1"

usage() {
  echo "Usage: ./dev.sh <command>"
  echo ""
  echo "Local Docker:"
  echo "  up        Start backend container at http://localhost:9090"
  echo "  build     Build backend image with --no-cache"
  echo "  down      Stop and remove local containers"
  echo "  restart   No-cache rebuild + restart"
  echo "  logs      Tail backend logs"
  echo "  shell     Open a shell inside the backend container"
  echo ""
  echo "Production Docker:"
  echo "  prod-up   Build and start nginx + backend + certbot"
  echo "  prod-down Stop and remove production containers"
  echo ""
  echo "Utility:"
  echo "  ps        Show local compose status"
  echo "  clean     Remove stopped containers and dangling images"
  echo ""
  echo "Backend local venv commands remain available at ./backend/dev.sh"
}

case "$1" in
  up)
    docker compose -f "$COMPOSE_LOCAL" up -d
    echo "Backend running at http://localhost:9090"
    echo "Swagger UI at http://localhost:9090/docs"
    ;;
  build)
    docker compose -f "$COMPOSE_LOCAL" build --no-cache backend
    ;;
  down)
    docker compose -f "$COMPOSE_LOCAL" down
    ;;
  restart)
    docker compose -f "$COMPOSE_LOCAL" down
    docker compose -f "$COMPOSE_LOCAL" build --no-cache backend
    docker compose -f "$COMPOSE_LOCAL" up -d
    echo "Restarted. Logs: ./dev.sh logs"
    ;;
  logs)
    docker logs -f "$LOCAL_CONTAINER"
    ;;
  shell)
    docker exec -it "$LOCAL_CONTAINER" /bin/bash
    ;;
  prod-up)
    docker compose -f "$COMPOSE_PROD" up --build -d
    ;;
  prod-down)
    docker compose -f "$COMPOSE_PROD" down
    ;;
  ps)
    docker compose -f "$COMPOSE_LOCAL" ps
    ;;
  clean)
    docker container prune -f
    docker image prune -f
    ;;
  *)
    usage
    ;;
esac
