#!/usr/bin/env sh
set -eu

mkdir -p /app/.interview_agent /home/interview/.cache/huggingface

for directory in /app/.interview_agent /home/interview/.cache/huggingface; do
  marker="$directory/.permissions-ready"
  if [ ! -f "$marker" ]; then
    chown -R interview:interview "$directory"
    touch "$marker"
    chown interview:interview "$marker"
  fi
done

exec gosu interview "$@"
