#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="${RELEASE_STAMP:-$(date +%Y%m%d-%H%M%S)}"
PACKAGE_NAME="${PACKAGE_NAME:-InterviewAgent-full-source-${STAMP}}"
OUTPUT_DIR="${OUTPUT_DIR:-$(dirname "$ROOT_DIR")/source-artifacts}"
ARCHIVE_PATH="$OUTPUT_DIR/${PACKAGE_NAME}.zip"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/interview-agent-source.XXXXXX")"
STAGE_DIR="$TEMP_DIR/$PACKAGE_NAME"

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

# Preserve every source surface and project document. Only generated
# dependencies/build output, credentials, local user data, and personal
# knowledge are excluded from the distributable source archive.
rsync -a \
  --include='/.env.example' \
  --include='/deploy/.env.production.example' \
  --exclude='/.git/' \
  --exclude='/.codebase-memory/' \
  --exclude='/.interview_agent/' \
  --exclude='/backend/.interview_agent/' \
  --exclude='/backups/' \
  --exclude='/release-artifacts/' \
  --exclude='/source-artifacts/' \
  --exclude='/knowledge_base/interview/' \
  --exclude='/.env*' \
  --exclude='node_modules/' \
  --exclude='Pods/' \
  --exclude='.swiftpm/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='.gradle/' \
  --exclude='.hvigor/' \
  --exclude='DerivedData/' \
  --exclude='xcuserdata/' \
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
cat > "$STAGE_DIR/SOURCE_PACKAGE_MANIFEST.txt" <<EOF
Interview Agent complete source package
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Revision: $REVISION

Included source surfaces:
- desktop web and Electron application
- Android, iOS, HarmonyOS, and mini program clients
- backend, database migrations, tests, and examples
- shared packages, API contracts, scripts, deployment files, and documentation
- non-personal public knowledge-base content and product specifications

Excluded by design:
- installed dependencies and generated build/cache output
- Git history and generated codebase graph cache
- local credentials, databases, uploads, backups, and test runtime output
- knowledge_base/interview personal content

Install dependencies locally with the repository lockfiles, or deploy directly:
  PUBLIC_URL=https://example.com ./deploy/stack.sh init
  edit .env.production and configure at least one model provider key
  ./deploy/stack.sh deploy
EOF

(
  cd "$TEMP_DIR"
  zip -qry "$ARCHIVE_PATH" "$PACKAGE_NAME"
)

FORBIDDEN_PATTERN='(^|/)(node_modules|Pods|\.swiftpm|\.venv|venv|__pycache__|\.pytest_cache|\.interview_agent|backups|release-artifacts|source-artifacts|knowledge_base/interview)(/|$)|(^|/)\.env\.production$|\.(db|sqlite|sqlite3|log|pem|key)$'
if unzip -Z1 "$ARCHIVE_PATH" | grep -E "$FORBIDDEN_PATTERN" >/dev/null; then
  printf 'Source package validation failed: forbidden files found in %s\n' "$ARCHIVE_PATH" >&2
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
