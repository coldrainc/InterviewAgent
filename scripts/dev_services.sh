#!/usr/bin/env bash
set -euo pipefail

command="${1:-up}"

compose_cmd=()
if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
fi

if [[ ${#compose_cmd[@]} -gt 0 ]]; then
  if [[ "$command" == "up" ]]; then
    "${compose_cmd[@]}" up -d postgres qdrant minio
  elif [[ "$command" == "down" ]]; then
    "${compose_cmd[@]}" down
  else
    echo "Unsupported command: $command" >&2
    exit 2
  fi
  exit 0
fi

start_or_create() {
  local name="$1"
  shift
  if docker start "$name" >/dev/null 2>&1; then
    echo "$name started"
  else
    docker run -d --name "$name" "$@"
  fi
}

if [[ "$command" == "up" ]]; then
  docker volume create interview_agent_postgres >/dev/null
  docker volume create qdrant_storage >/dev/null
  docker volume create interview_agent_minio >/dev/null

  start_or_create interview-agent-postgres \
    -e POSTGRES_DB=interview_agent \
    -e POSTGRES_USER=interview_agent \
    -e POSTGRES_PASSWORD=interview_agent \
    -p 5432:5432 \
    -v interview_agent_postgres:/var/lib/postgresql/data \
    postgres:16-alpine

  start_or_create interview-agent-qdrant \
    -p 6333:6333 \
    -p 6334:6334 \
    -v qdrant_storage:/qdrant/storage \
    qdrant/qdrant:v1.11.5

  start_or_create interview-agent-minio \
    -e MINIO_ROOT_USER=interview_agent \
    -e MINIO_ROOT_PASSWORD=interview_agent_password \
    -p 9002:9000 \
    -p 9003:9001 \
    -v interview_agent_minio:/data \
    minio/minio:RELEASE.2024-07-16T23-46-41Z server /data --console-address ":9001"
elif [[ "$command" == "down" ]]; then
  docker stop interview-agent-postgres interview-agent-qdrant interview-agent-minio
else
  echo "Unsupported command: $command" >&2
  exit 2
fi
