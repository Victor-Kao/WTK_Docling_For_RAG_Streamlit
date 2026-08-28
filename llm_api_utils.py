"""Cloud LLM API document parsing via LlamaIndex (no local models / no Hugging Face)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
import requests
import streamlit as st

# Keep uploads within typical API limits (no local model download).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
MAX_PDF_VISION_PAGES = 40
PDF_VISION_DPI = 144
PDF_VISION_MAX_DIM = 2048
DEFAULT_API_PATH = "chat/completions"
PDF_VISION_MODES = ("auto", "always", "text_only")

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
PROMPT_VISION = (
    "You are viewing a document page or image. "
    "Extract all visible content as clean Markdown for RAG indexing. "
    "Transcribe text in photos, scans, charts, diagrams, and tables. "
    "Preserve headings, lists, tables (markdown tables), and reading order. "
    "Output only the document content — no commentary or wrapper text."
)


@dataclass
class LlmApiConfig:
    """User-supplied remote LLM endpoint (any company gateway)."""

    api_base_url: str
    api_key: str
    model: str
    api_path: str = DEFAULT_API_PATH
    pdf_vision_mode: str = "auto"

    def validate(self) -> None:
        if not (self.api_base_url or "").strip():
            raise ValueError(
                "API base URL is required (e.g. https://gateway.company.com/v1)."
            )
        if not (self.api_key or "").strip():
            raise ValueError("API key is required.")
        if not (self.model or "").strip():
            raise ValueError("Model name is required.")
        if not (self.api_path or "").strip():
            raise ValueError("API path is required (default: chat/completions).")
        if self.pdf_vision_mode not in PDF_VISION_MODES:
            raise ValueError(
                f"PDF vision mode must be one of: {', '.join(PDF_VISION_MODES)}."
            )

    def completions_url(self) -> str:
        base = self.api_base_url.strip().rstrip("/")
        path = self.api_path.strip().lstrip("/")
        return f"{base}/{path}"


def _config_from_session(key_prefix: str) -> LlmApiConfig:
    return LlmApiConfig(
        api_base_url=str(st.session_state.get(f"{key_prefix}llm_base_url", "")).strip(),
        api_key=str(st.session_state.get(f"{key_prefix}llm_api_key", "")).strip(),
        model=str(st.session_state.get(f"{key_prefix}llm_model", "")).strip(),
        api_path=str(
            st.session_state.get(f"{key_prefix}llm_api_path", DEFAULT_API_PATH)
        ).strip(),
        pdf_vision_mode=str(
            st.session_state.get(f"{key_prefix}llm_pdf_vision", "auto")
        ).strip(),
    )


def render_llm_api_settings(*, key_prefix: str = "") -> LlmApiConfig:
    """Sidebar fields — user defines endpoint, model, and path (no vendor preset)."""
    st.subheader("LLM API")
    st.caption(
        "Connect any company LLM that exposes an HTTP API. "
        "No Hugging Face downloads and no local model weights."
    )
    api_base_url = st.text_input(
        "API base URL",
        value="",
        key=f"{key_prefix}llm_base_url",
        placeholder="https://your-company-gateway.example.com/v1",
        help="Root URL for the API (usually ends with /v1).",
    )
    api_path = st.text_input(
        "API path",
        value=DEFAULT_API_PATH,
        key=f"{key_prefix}llm_api_path",
        help="Path appended to base URL. Common: chat/completions",
    )
    model = st.text_input(
        "Model name",
        value="",
        key=f"{key_prefix}llm_model",
        placeholder="your-company-model-id",
        help="Exact model id from your IT / API portal.",
    )
    api_key = st.text_input(
        "API key",
        type="password",
        key=f"{key_prefix}llm_api_key",
        help="Stored in this browser session only — not saved to git.",
    )
    pdf_vision_mode = st.selectbox(
        "PDF vision",
        options=list(PDF_VISION_MODES),
        index=0,
        format_func=lambda value: {
            "auto": "Auto — vision when pages look scanned or image-heavy",
            "always": "Always — send each page as an image to the model",
            "text_only": "Text only — faster; ignores pictures in PDFs",
        }[value],
        key=f"{key_prefix}llm_pdf_vision",
        help=(
            "Standalone image files always use vision. "
            "Requires a multimodal model (e.g. gemini-2.0-flash, gpt-4o)."
        ),
    )
    if st.button(
        "Test API connection",
        key=f"{key_prefix}llm_test_btn",
        help="Sends a tiny prompt to verify URL, key, and model.",
    ):
        try:
            cfg = _config_from_session(key_prefix)
            cfg.validate()
            reply = test_llm_connection(cfg)
            st.success(f"API OK — model replied: {reply[:300]}")
        except Exception as exc:
            st.error(f"API test failed: {exc}")

    return LlmApiConfig(
        api_base_url=api_base_url.strip(),
        api_key=api_key.strip(),
        model=model.strip(),
        api_path=api_path.strip() or DEFAULT_API_PATH,
        pdf_vision_mode=pdf_vision_mode,
    )


def _get_openai_like_llm(config: LlmApiConfig):
    try:
        from llama_index.llms.openai_like import OpenAILike
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex OpenAI-like LLM is not installed. Run: "
            "pip install llama-index-core llama-index-llms-openai-like"
        ) from exc

    return OpenAILike(
        model=config.model,
        api_base=config.api_base_url.rstrip("/"),
        api_key=config.api_key,
        is_chat_model=True,
        temperature=0.1,
        max_tokens=8192,
        timeout=300.0,
    )


def test_llm_connection(config: LlmApiConfig) -> str:
    """Ping the configured API with a minimal prompt."""
    config.validate()
    return _complete_text(config, "Reply with exactly: OK", system_hint=None)


def _complete_text(
    config: LlmApiConfig,
    user_content: str,
    *,
    system_hint: str | None = "You extract document content accurately.",
) -> str:
    llm = _get_openai_like_llm(config)
    try:
        from llama_index.core.llms import ChatMessage, MessageRole

        messages: list[ChatMessage] = []
        if system_hint:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_hint))
        messages.append(ChatMessage(role=MessageRole.USER, content=user_content))
        response = llm.chat(messages)
        text = getattr(response, "message", None)
        content = getattr(text, "content", None) if text is not None else None
        if content is None:
            content = getattr(response, "text", None) or str(response)
    except Exception:
        # Some gateways only implement /chat/completions via raw HTTP.
        content = _chat_completions_http(
            config,
            messages_body=_build_messages(user_content, system_hint),
        )
    result = (content or "").strip()
    if not result:
        raise RuntimeError("LLM API returned an empty response.")
    return result


def _build_messages(
    user_content: str,
    system_hint: str | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system_hint:
        messages.append({"role": "system", "content": system_hint})
    messages.append({"role": "user", "content": user_content})
    return messages


def _chat_completions_http(
    config: LlmApiConfig,
    *,
    messages_body: list[dict[str, Any]],
) -> str:
    payload = {
        "model": config.model,
        "messages": messages_body,
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            config.completions_url(),
            headers=headers,
            json=payload,
            timeout=300,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"LLM API request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise RuntimeError(
            f"LLM API error {resp.status_code} at {config.completions_url()}: "
            f"{resp.text[:500]}"
        )

    data = resp.json()
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM API response: {data!r}") from exc


def _vision_http(
    config: LlmApiConfig,
    *,
    prompt: str,
    image_bytes: bytes,
    image_mime: str,
) -> str:
    """Vision request for gateways that support OpenAI-style image_url messages."""
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    messages = [
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
    ]
    return _chat_completions_http(config, messages_body=messages)


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


def _extract_pdf_page_texts(raw: bytes) -> list[str]:
    doc = pymupdf.open(stream=raw, filetype="pdf")
    try:
        texts: list[str] = []
        for page in doc:
            try:
                texts.append(page.get_text("text") or "")
            except Exception:
                texts.append("")
        return texts
    finally:
        doc.close()


def _should_use_pdf_vision(page_texts: list[str], mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "text_only":
        return False
    if not page_texts:
        return True
    stripped = [text.strip() for text in page_texts]
    if not any(stripped):
        return True
    sparse_pages = sum(1 for text in stripped if len(text) < 40)
    if sparse_pages >= max(1, len(stripped) // 2):
        return True
    average_chars = sum(len(text) for text in stripped) / len(stripped)
    return average_chars < 80


def _render_pdf_page_pngs(raw: bytes) -> list[bytes]:
    doc = pymupdf.open(stream=raw, filetype="pdf")
    try:
        page_count = doc.page_count
        if page_count > MAX_PDF_VISION_PAGES:
            raise ValueError(
                f"PDF has {page_count} pages; LLM vision supports up to "
                f"{MAX_PDF_VISION_PAGES} pages. Use Docling or split the file."
            )
        images: list[bytes] = []
        for page in doc:
            rect = page.rect
            zoom = PDF_VISION_DPI / 72.0
            longest = max(rect.width, rect.height)
            if longest * zoom > PDF_VISION_MAX_DIM:
                zoom = PDF_VISION_MAX_DIM / longest
            matrix = pymupdf.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            images.append(pixmap.tobytes("png"))
        return images
    finally:
        doc.close()


def _parse_pdf_with_vision(
    name: str,
    raw: bytes,
    *,
    config: LlmApiConfig,
    output_format: str,
) -> str:
    page_images = _render_pdf_page_pngs(raw)
    page_count = len(page_images)
    page_sections: list[str] = []
    page_records: list[dict[str, Any]] = []

    for index, image_bytes in enumerate(page_images, start=1):
        page_prompt = (
            f"{PROMPT_VISION}\n\n"
            f"This is page {index} of {page_count} from PDF `{name}`."
        )
        page_text = _vision_http(
            config,
            prompt=page_prompt,
            image_bytes=image_bytes,
            image_mime="image/png",
        )
        page_sections.append(f"## Page {index}\n\n{page_text.strip()}")
        page_records.append({"page": index, "markdown": page_text.strip()})

    if output_format == "JSON":
        return json.dumps(
            {
                "source": name,
                "parser": "llm_api_vision",
                "model": config.model,
                "api_base_url": config.api_base_url,
                "pages": page_records,
            },
            indent=2,
            ensure_ascii=False,
        )

    return "\n\n".join(page_sections).strip()


def _mime_for_extension(ext: str) -> str:
    mapping = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }
    return mapping.get(ext, "application/octet-stream")


def _prepare_document_text(name: str, raw: bytes, ext: str) -> str:
    if ext == "pdf":
        text = _extract_pdf_text(raw)
        if not text.strip():
            raise ValueError(
                "This PDF has no extractable text. Use Docling/LiteParse with OCR, "
                "or a vision-capable model if your API supports image input."
            )
        return _truncate_text(text)

    if ext in TEXT_LIKE_EXTENSIONS:
        return _truncate_text(raw.decode("utf-8", errors="replace"))

    raise ValueError(
        f"Cannot extract plain text from `.{ext}` for LLM API. "
        "Use Docling for Office files, or upload PDF/text/image types."
    )


def parse_with_llm_api(
    name: str,
    raw: bytes,
    *,
    config: LlmApiConfig,
    output_format: str,
) -> tuple[str, str, str]:
    """Parse document bytes via a user-configured remote LLM API."""
    config.validate()

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB API limit."
        )

    ext = Path(name).suffix.lstrip(".").lower()
    stem = Path(name).stem
    prompt = PROMPT_JSON if output_format == "JSON" else PROMPT_MARKDOWN

    if ext in IMAGE_EXTENSIONS:
        try:
            result_text = _vision_http(
                config,
                prompt=PROMPT_VISION,
                image_bytes=raw,
                image_mime=_mime_for_extension(ext),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Image parsing via API failed: {exc}. "
                "Your gateway may not support vision; try Docling or a text-based file."
            ) from exc
    elif ext == "pdf":
        page_texts = _extract_pdf_page_texts(raw)
        use_vision = _should_use_pdf_vision(page_texts, config.pdf_vision_mode)
        if use_vision:
            try:
                result_text = _parse_pdf_with_vision(
                    name,
                    raw,
                    config=config,
                    output_format=output_format,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"PDF vision parsing failed: {exc}. "
                    "Confirm your model supports image input, or set PDF vision to "
                    "Text only."
                ) from exc
        else:
            document_text = _truncate_text("\n\n".join(page_texts).strip())
            if not document_text.strip():
                raise ValueError(
                    "This PDF has no extractable text. Set PDF vision to Auto or "
                    "Always, or use Docling/LiteParse with OCR."
                )
            result_text = _complete_text(
                config,
                f"{prompt}\n\n---\n\n{document_text}",
            )
    else:
        document_text = _prepare_document_text(name, raw, ext)
        result_text = _complete_text(
            config,
            f"{prompt}\n\n---\n\n{document_text}",
        )

    if output_format == "JSON":
        try:
            json.loads(result_text)
            content = result_text
        except json.JSONDecodeError:
            content = json.dumps(
                {
                    "source": name,
                    "parser": "llm_api",
                    "model": config.model,
                    "api_base_url": config.api_base_url,
                    "text": result_text,
                },
                indent=2,
                ensure_ascii=False,
            )
        return content, f"{stem}.json", "application/json"

    return result_text.rstrip() + "\n", f"{stem}.md", "text/markdown"
