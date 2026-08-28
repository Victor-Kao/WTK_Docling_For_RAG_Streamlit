"""Cloud LLM API document parsing (no local models / no Hugging Face)."""

from __future__ import annotations

import base64
import json
import mimetypes
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
import requests
import streamlit as st

PROVIDER_GEMINI = "Gemini"
PROVIDER_OPENAI = "OpenAI-compatible"
LLM_PROVIDERS = [PROVIDER_GEMINI, PROVIDER_OPENAI]

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o"

# Keep uploads within typical API limits (no local model download).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 120_000

TEXT_LIKE_EXTENSIONS = {
    "txt",
    "md",
    "csv",
    "json",
    "html",
    "htm",
}
IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "webp",
    "gif",
}

PROMPT_MARKDOWN = (
    "Extract the document content as clean Markdown for RAG indexing. "
    "Preserve headings, lists, tables (markdown tables), and reading order. "
    "Output only the document content — no commentary or wrapper text."
)
PROMPT_JSON = (
    "Extract the document into structured JSON with keys: "
    "title (string), sections (array of {heading, content}), "
    "tables (array of markdown table strings), plain_text (string). "
    "Return valid JSON only, no markdown fences."
)


@dataclass
class LlmApiConfig:
    provider: str
    api_key: str
    model: str
    base_url: str = ""

    def validate(self) -> None:
        if not (self.api_key or "").strip():
            raise ValueError("LLM API key is required. Enter your company API key in Settings.")
        if not (self.model or "").strip():
            raise ValueError("LLM model name is required.")
        if self.provider == PROVIDER_OPENAI and not (self.base_url or "").strip():
            raise ValueError(
                "OpenAI-compatible provider needs an API base URL "
                "(e.g. your company gateway /v1 endpoint)."
            )


def default_model_for_provider(provider: str) -> str:
    if provider == PROVIDER_GEMINI:
        return DEFAULT_GEMINI_MODEL
    return DEFAULT_OPENAI_MODEL


def render_llm_api_settings(*, key_prefix: str = "") -> LlmApiConfig:
    """Sidebar fields for cloud LLM parsing."""
    st.subheader("LLM API")
    provider = st.selectbox(
        "API provider",
        options=LLM_PROVIDERS,
        key=f"{key_prefix}llm_provider",
        help="Uses only HTTP APIs — no Hugging Face or local model downloads.",
    )
    api_key = st.text_input(
        "API key",
        type="password",
        key=f"{key_prefix}llm_api_key",
        help="Paste your company-issued API key. Stored in this browser session only.",
    )
    model = st.text_input(
        "Model",
        value=default_model_for_provider(provider),
        key=f"{key_prefix}llm_model",
        help="Examples: gemini-2.0-flash, gemini-1.5-flash, gpt-4o",
    )
    base_url = st.text_input(
        "API base URL",
        value="",
        disabled=provider != PROVIDER_OPENAI,
        key=f"{key_prefix}llm_base_url",
        placeholder="https://your-company-gateway.example.com/v1",
        help="Required for OpenAI-compatible company gateways.",
    )
    st.caption(
        "API-only parsing: PDF/images sent to the cloud API; text files sent as text. "
        "No Hugging Face or on-device models."
    )
    return LlmApiConfig(
        provider=provider,
        api_key=api_key.strip(),
        model=model.strip(),
        base_url=base_url.strip().rstrip("/"),
    )


def _mime_for_extension(ext: str) -> str:
    guessed = mimetypes.types_map.get(f".{ext}")
    if guessed:
        return guessed
    fallback = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "doc": "application/msword",
        "ppt": "application/vnd.ms-powerpoint",
        "xls": "application/vnd.ms-excel",
        "csv": "text/csv",
    }
    return fallback.get(ext, "application/octet-stream")


def _truncate_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[... truncated for API size limit ...]"


def _extract_pdf_text(raw: bytes) -> str:
    doc = pymupdf.open(stream=raw, filetype="pdf")
    try:
        parts: list[str] = []
        for page in doc:
            try:
                parts.append(page.get_text("text") or "")
            except Exception:
                continue
        return "\n\n".join(parts).strip()
    finally:
        doc.close()


def _prepare_text_payload(name: str, raw: bytes, ext: str) -> str:
    if ext == "pdf":
        text = _extract_pdf_text(raw)
        if not text.strip():
            raise ValueError(
                "PDF has no extractable text. Use Docling/LiteParse with OCR, "
                "or Gemini provider which can read PDF files directly."
            )
        return _truncate_text(text)

    if ext in TEXT_LIKE_EXTENSIONS:
        text = raw.decode("utf-8", errors="replace")
        return _truncate_text(text)

    raise ValueError(
        f"Cannot send `.{ext}` as plain text to an OpenAI-compatible endpoint. "
        "Use the Gemini provider for PDF/images, or pick Docling for Office files."
    )


def _gemini_generate(
    config: LlmApiConfig,
    *,
    prompt: str,
    file_path: Path | None = None,
    mime_type: str | None = None,
    text_content: str | None = None,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=config.api_key)
    contents: list[Any] = []

    if file_path is not None:
        uploaded = client.files.upload(file=str(file_path))
        contents.append(uploaded)
    if text_content is not None:
        contents.append(text_content)

    contents.append(prompt)

    response = client.models.generate_content(
        model=config.model,
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.1),
    )
    text = getattr(response, "text", None) or ""
    if not text.strip():
        raise RuntimeError("Gemini API returned an empty response.")
    return text.strip()


def _openai_compatible_generate(
    config: LlmApiConfig,
    *,
    prompt: str,
    text_content: str | None = None,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> str:
    url = f"{config.base_url}/chat/completions"
    messages: list[dict[str, Any]] = []

    if image_bytes is not None and image_mime:
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{b64}"},
                    },
                ],
            }
        )
    else:
        body_text = text_content or ""
        messages.append(
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\n{body_text}",
            }
        )

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=300)
    except requests.RequestException as exc:
        raise RuntimeError(f"LLM API request failed: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"LLM API error {resp.status_code}: {detail}")

    data = resp.json()
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM API response: {data!r}") from exc


def parse_with_llm_api(
    name: str,
    raw: bytes,
    *,
    config: LlmApiConfig,
    output_format: str,
) -> tuple[str, str, str]:
    """Parse document bytes via a cloud LLM API only (no local models)."""
    config.validate()

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB API limit."
        )

    ext = Path(name).suffix.lstrip(".").lower()
    stem = Path(name).stem
    prompt = PROMPT_JSON if output_format == "JSON" else PROMPT_MARKDOWN

    tmp_path: str | None = None
    try:
        if config.provider == PROVIDER_GEMINI:
            # Prefer native file upload for PDF / images / Office when possible.
            if ext in IMAGE_EXTENSIONS or ext == "pdf" or ext in {
                "docx",
                "pptx",
                "xlsx",
                "doc",
                "ppt",
                "xls",
            }:
                suffix = Path(name).suffix or f".{ext}"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(raw)
                    tmp_path = tmp.name
                result_text = _gemini_generate(
                    config,
                    prompt=prompt,
                    file_path=Path(tmp_path),
                    mime_type=_mime_for_extension(ext),
                )
            elif ext in TEXT_LIKE_EXTENSIONS:
                text = _truncate_text(raw.decode("utf-8", errors="replace"))
                result_text = _gemini_generate(
                    config,
                    prompt=prompt,
                    text_content=text,
                )
            else:
                raise ValueError(
                    f"LLM API does not support `.{ext}`. Use Docling or another parser."
                )
        else:
            # OpenAI-compatible: text + vision images only.
            if ext in IMAGE_EXTENSIONS:
                result_text = _openai_compatible_generate(
                    config,
                    prompt=prompt,
                    image_bytes=raw,
                    image_mime=_mime_for_extension(ext),
                )
            else:
                text_payload = _prepare_text_payload(name, raw, ext)
                result_text = _openai_compatible_generate(
                    config,
                    prompt=prompt,
                    text_content=text_payload,
                )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    if output_format == "JSON":
        try:
            json.loads(result_text)
            content = result_text
        except json.JSONDecodeError:
            content = json.dumps(
                {
                    "source": name,
                    "parser": "llm_api",
                    "provider": config.provider,
                    "model": config.model,
                    "text": result_text,
                },
                indent=2,
                ensure_ascii=False,
            )
        return content, f"{stem}.json", "application/json"

    return result_text.rstrip() + "\n", f"{stem}.md", "text/markdown"
