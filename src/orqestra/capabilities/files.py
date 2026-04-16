"""Upload processing — text extraction from documents and vision analysis for images."""

from __future__ import annotations

import base64
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import OpenAI

log = logging.getLogger(__name__)

MAX_TEXT_CHARS = 50_000

# Vision-capable uploads (OpenAI-style image_url)
_SUPPORTED_IMAGE_MIMES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
})


@dataclass
class UploadResult:
    """Result of processing an uploaded file for injection into the chat."""

    context_text: str
    filename: str
    mime: str
    is_image: bool


def _truncate(text: str) -> str:
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[: MAX_TEXT_CHARS - 20] + "\n\n[… truncated …]"


def extract_text(path: Path) -> str:
    """Extract plain text from PDF, DOCX, or text-like files."""
    suffix = path.suffix.lower()

    if suffix == ".doc":
        raise ValueError(
            "Legacy Word .doc is not supported. Please save as .docx or export as PDF."
        )

    if suffix == ".pdf":
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return _truncate("\n\n".join(parts))

    if suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return _truncate("\n\n".join(paras))

    if suffix in (
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".html",
        ".htm",
        ".rst",
    ) or suffix == "":
        raw = path.read_text(encoding="utf-8", errors="replace")
        return _truncate(raw)

    # Fallback: try UTF-8 for unknown extensions
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if raw.strip():
            return _truncate(raw)
    except OSError:
        pass

    raise ValueError(
        f"Unsupported file type ({suffix or 'no extension'}). "
        "Supported: PDF, DOCX, TXT, Markdown, CSV, JSON, YAML, HTML."
    )


def analyze_image(path: Path, mime: str, llm: Any, model: str) -> str:
    """Describe image content using the configured vision-capable chat model."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    safe_mime = mime if mime in _SUPPORTED_IMAGE_MIMES else "image/png"
    url = f"data:{safe_mime};base64,{b64}"

    prompt = (
        "Describe this image in detail. Transcribe any visible text verbatim. "
        "For screenshots: explain the UI, context, and relevant information. "
        "Respond in the same language as the visible text when possible; otherwise English."
    )

    response = llm.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
        max_tokens=4096,
    )
    choice = response.choices[0].message
    return (choice.content or "").strip()


def _normalize_mime(path: Path, mime: str | None, filename: str) -> str:
    if mime and mime != "application/octet-stream":
        return mime.split(";")[0].strip().lower()
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    guessed2, _ = mimetypes.guess_type(str(path))
    return guessed2 or "application/octet-stream"


def process_upload(
    path: Path,
    mime: str | None,
    filename: str,
    llm: Any,
    model: str,
) -> UploadResult:
    """Extract text or run vision analysis; returns payload for the orchestrator."""
    norm_mime = _normalize_mime(path, mime, filename)
    safe_name = filename or path.name

    if norm_mime.startswith("image/"):
        if norm_mime not in _SUPPORTED_IMAGE_MIMES:
            ext = path.suffix.lower()
            if ext in (".jpg", ".jpeg"):
                norm_mime = "image/jpeg"
            elif ext == ".png":
                norm_mime = "image/png"
            elif ext == ".gif":
                norm_mime = "image/gif"
            elif ext == ".webp":
                norm_mime = "image/webp"
            else:
                raise ValueError(
                    f"Unsupported image format: {norm_mime}. "
                    "Allowed: JPEG, PNG, GIF, WebP."
                )

        try:
            text = analyze_image(path, norm_mime, llm, model)
        except Exception as exc:
            log.exception("Vision analysis failed")
            raise ValueError(f"Image analysis failed: {exc}") from exc

        return UploadResult(
            context_text=text,
            filename=safe_name,
            mime=norm_mime,
            is_image=True,
        )

    text = extract_text(path)
    return UploadResult(
        context_text=text,
        filename=safe_name,
        mime=norm_mime,
        is_image=False,
    )


def format_upload_user_message(
    filename: str,
    context_text: str,
    is_image: bool,
    user_message: str = "",
) -> str:
    """Build the full user message sent to the orchestrator (Web + Telegram)."""
    kind = "Image analysis" if is_image else "File"
    lines = [
        f"[{kind}: {filename}]",
        "",
        context_text.strip(),
        "",
        "---",
        "Note: If the user explicitly wants this content saved to the wiki, "
        "use kb_write with an appropriate path under wiki/ (e.g. wiki/wissen/…).",
    ]
    um = user_message.strip()
    if um:
        lines.extend(["", "User message / task:", um])
    return "\n".join(lines)
