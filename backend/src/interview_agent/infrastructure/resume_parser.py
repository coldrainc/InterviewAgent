from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


MAX_RESUME_BYTES = 10 * 1024 * 1024
MAX_RESUME_CHARS = 30000
SUPPORTED_MARKDOWN_EXTENSIONS = {".md", ".markdown"}


class ResumeParseError(ValueError):
    """Raised when a resume file cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedResume:
    filename: str
    file_type: str
    text: str
    summary: str
    truncated: bool = False


def parse_resume_base64(filename: str, content_base64: str) -> ParsedResume:
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise ResumeParseError("简历文件内容不是有效的 base64。") from exc
    return parse_resume_bytes(filename, raw)


def parse_resume_bytes(filename: str, content: bytes) -> ParsedResume:
    clean_name = Path(filename).name
    suffix = Path(clean_name).suffix.lower()
    if not content:
        raise ResumeParseError("简历文件为空。")
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeParseError("简历文件超过 10MB，请先压缩或导出为较小的 PDF/Markdown。")

    if suffix in SUPPORTED_MARKDOWN_EXTENSIONS:
        text = _decode_markdown(content)
        file_type = "markdown"
    elif suffix == ".pdf":
        text = _extract_pdf_text(content)
        file_type = "pdf"
    else:
        raise ResumeParseError("仅支持 PDF、Markdown 简历文件。")

    normalized = _normalize_text(text)
    if not normalized:
        raise ResumeParseError("没有从简历中解析出可用文本。")

    truncated = len(normalized) > MAX_RESUME_CHARS
    if truncated:
        normalized = normalized[:MAX_RESUME_CHARS].rstrip()

    return ParsedResume(
        filename=clean_name,
        file_type=file_type,
        text=normalized,
        summary=build_resume_summary(normalized),
        truncated=truncated,
    )


def build_resume_summary(text: str, max_lines: int = 8, max_chars: int = 900) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        clean = line.strip(" \t#-*•")
        if not clean:
            continue
        if len(clean) < 2 and not any(char.isdigit() for char in clean):
            continue
        lines.append(clean)
        if len(lines) >= max_lines:
            break
    summary = "\n".join(lines)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip()
    return summary


def _decode_markdown(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ResumeParseError("Markdown 简历编码无法识别，请使用 UTF-8。")


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ResumeParseError("当前环境缺少 pypdf，无法解析 PDF 简历。请运行 make install。") from exc

    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        raise ResumeParseError("PDF 简历无法打开，请确认文件没有损坏或加密。") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ResumeParseError("PDF 简历已加密，请提供未加密版本。") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages.append(page_text)
    return "\n\n".join(pages)


def _normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    compact: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line
        if blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = blank
    return "\n".join(compact).strip()
