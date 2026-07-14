from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from interview_agent.domain.resume import StoredResume, stored_resume_to_payload
from interview_agent.infrastructure.resume_parser import ParsedResume, parse_resume_bytes


class ResumeStore:
    def __init__(self, root: Path = Path(".interview_agent/resumes")) -> None:
        self.root = root
        self.files_root = root / "files"
        self.records_root = root / "records"
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.records_root.mkdir(parents=True, exist_ok=True)

    def save_base64(
        self,
        filename: str,
        content_base64: str,
        source_path: str | None = None,
    ) -> StoredResume:
        raw = base64.b64decode(content_base64, validate=True)
        return self.save_bytes(filename, raw, source_path=source_path)

    def save_bytes(
        self,
        filename: str,
        content: bytes,
        source_path: str | None = None,
    ) -> StoredResume:
        resume_id = hashlib.sha256(content).hexdigest()
        parsed = parse_resume_bytes(filename, content)
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(resume_id)
        created_at = existing.created_at if existing else now

        suffix = Path(parsed.filename).suffix.lower()
        file_path = self.files_root / f"{resume_id}{suffix}"
        if not file_path.exists():
            file_path.write_bytes(content)

        record = StoredResume(
            id=resume_id,
            filename=parsed.filename,
            file_type=parsed.file_type,
            summary=parsed.summary,
            text=parsed.text,
            truncated=parsed.truncated,
            created_at=created_at,
            updated_at=now,
            source_path=source_path,
        )
        self._record_path(resume_id).write_text(
            json.dumps(stored_resume_to_payload(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def list(self) -> list[StoredResume]:
        records: list[StoredResume] = []
        for path in sorted(self.records_root.glob("*.json")):
            try:
                records.append(self._read_record(path))
            except Exception:
                continue
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def get(self, resume_id: str) -> StoredResume | None:
        path = self._record_path(resume_id)
        if not path.exists():
            return None
        return self._read_record(path)

    def _record_path(self, resume_id: str) -> Path:
        return self.records_root / f"{resume_id}.json"

    def _read_record(self, path: Path) -> StoredResume:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StoredResume(**payload)
