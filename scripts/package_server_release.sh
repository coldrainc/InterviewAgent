#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="${RELEASE_STAMP:-$(date +%Y%m%d-%H%M%S)}"
RELEASE_NAME="${RELEASE_NAME:-InterviewAgent-server-${STAMP}}"
OUTPUT_DIR="${OUTPUT_DIR:-$(dirname "$ROOT_DIR")/release-artifacts}"
ARCHIVE_PATH="$OUTPUT_DIR/${RELEASE_NAME}.zip"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/interview-agent-release.XXXXXX")"
STAGE_DIR="$TEMP_DIR/$RELEASE_NAME"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

require_command rsync
require_command zip
require_command unzip

mkdir -p "$OUTPUT_DIR" "$STAGE_DIR"
rm -f "$ARCHIVE_PATH" "$ARCHIVE_PATH.sha256"

# Copy source while excluding installed dependencies, build output, private
# runtime data, local credentials, personal knowledge, and test artifacts.
rsync -a \
  --include='/.env.example' \
  --include='/deploy/.env.production.example' \
  --exclude='/.git/' \
  --exclude='/.github/' \
  --exclude='/.codebase-memory/' \
  --exclude='/.trae/' \
  --exclude='/AGENTS.md' \
  --exclude='/.interview_agent/' \
  --exclude='/backend/.interview_agent/' \
  --exclude='/backups/' \
  --exclude='/release-artifacts/' \
  --exclude='/knowledge_base/interview/' \
  --exclude='/.env*' \
  --exclude='node_modules/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='.gradle/' \
  --exclude='.hvigor/' \
  --exclude='DerivedData/' \
  --exclude='dist/' \
  --exclude='build/' \
  --exclude='out/' \
  --exclude='release/' \
  --exclude='dist-electron/' \
  --exclude='/tests/artifacts/' \
  --exclude='/tests/.runtime/' \
  --exclude='.DS_Store' \
  --exclude='*.py[co]' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3' \
  --exclude='*.log' \
  --exclude='*.pem' \
  --exclude='*.key' \
  --exclude='*.zip' \
  --exclude='*.tar' \
  --exclude='*.tar.gz' \
  "$ROOT_DIR/" "$STAGE_DIR/"

REVISION="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unversioned')"
cat > "$STAGE_DIR/PACKAGE_MANIFEST.txt" <<EOF
Interview Agent server source package
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Revision: $REVISION

This archive intentionally excludes installed dependencies, build caches,
local credentials, runtime databases, uploads, backups, test artifacts, and
knowledge_base/interview personal content.

Deployment:
  PUBLIC_URL=https://example.com ./deploy/stack.sh init
  edit .env.production and configure at least one model provider key
  ./deploy/stack.sh deploy
EOF

(
  cd "$TEMP_DIR"
  zip -qry "$ARCHIVE_PATH" "$RELEASE_NAME"
)

FORBIDDEN_PATTERN='(^|/)(node_modules|\.venv|venv|__pycache__|\.pytest_cache|\.interview_agent|backups|release-artifacts|knowledge_base/interview)(/|$)|(^|/)\.env\.production$|\.(db|sqlite|sqlite3|log|pem|key)$'
if unzip -Z1 "$ARCHIVE_PATH" | grep -E "$FORBIDDEN_PATTERN" >/dev/null; then
  printf 'Release validation failed: forbidden files found in %s\n' "$ARCHIVE_PATH" >&2
  unzip -Z1 "$ARCHIVE_PATH" | grep -E "$FORBIDDEN_PATTERN" >&2 || true
  rm -f "$ARCHIVE_PATH"
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  (cd "$OUTPUT_DIR" && shasum -a 256 "$(basename "$ARCHIVE_PATH")") > "$ARCHIVE_PATH.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$OUTPUT_DIR" && sha256sum "$(basename "$ARCHIVE_PATH")") > "$ARCHIVE_PATH.sha256"
fi

printf 'Created: %s\n' "$ARCHIVE_PATH"
printf 'Size:    %s\n' "$(du -h "$ARCHIVE_PATH" | awk '{print $1}')"
printf 'Files:   %s\n' "$(unzip -Z1 "$ARCHIVE_PATH" | wc -l | tr -d ' ')"
if [[ -f "$ARCHIVE_PATH.sha256" ]]; then
  printf 'SHA256:  %s\n' "$(awk '{print $1}' "$ARCHIVE_PATH.sha256")"
fi
