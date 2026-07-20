#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Import civil service exam questions into InterviewAgent API.")
    parser.add_argument("path", type=Path, help="JSON or CSV file path.")
    parser.add_argument("--api-base", default=os.getenv("INTERVIEW_PUBLIC_API_BASE", "https://www.aivago.cn/api"))
    parser.add_argument("--token", default=os.getenv("INTERVIEW_API_TOKEN", ""))
    args = parser.parse_args()

    questions = load_questions(args.path)
    if not questions:
        print("No questions found.", file=sys.stderr)
        return 1
    payload = json.dumps({"questions": questions}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{args.api_base.rstrip('/')}/civil-service/questions/import",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **({"Authorization": f"Bearer {args.token}"} if args.token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        print(response.read().decode("utf-8"))
    return 0


def load_questions(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("questions", [])
        return payload if isinstance(payload, list) else []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [normalize_csv_row(row) for row in csv.DictReader(handle)]
    raise ValueError("Only .json and .csv files are supported.")


def normalize_csv_row(row: dict[str, str]) -> dict:
    choices = []
    if row.get("choices"):
        choices = [item.strip() for item in row["choices"].split("|") if item.strip()]
    return {
        "source": row.get("source") or "csv_import",
        "source_url": row.get("source_url") or "",
        "exam_year": row.get("exam_year") or row.get("year"),
        "exam_name": row.get("exam_name") or "考公导入题",
        "subject": row.get("subject") or "xingce",
        "question_type": row.get("question_type") or row.get("type") or "综合训练",
        "prompt": row.get("prompt") or row.get("question") or "",
        "choices": choices,
        "answer": row.get("answer") or "",
        "explanation": row.get("explanation") or "",
        "difficulty": row.get("difficulty") or "medium",
        "tags": [item.strip() for item in (row.get("tags") or "").split("|") if item.strip()],
        "metadata": {},
    }


if __name__ == "__main__":
    raise SystemExit(main())
