#!/usr/bin/env sh
set -eu

cd /app/backend
alembic upgrade head
cd /app
exec interview-agent api --host 0.0.0.0 --port 8020
