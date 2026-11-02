"""Bounded document ingestion; extracted text and original bytes stay distinct."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse
from xml.etree import ElementTree
from zipfile import ZipFile

from .errors import EngineError

MAX_BYTES = 8_000_000
MAX_TEXT = 150_000


@dataclass
class Document:
    text: str
    raw: bytes
    mime: str
    reference: str
    partial: bool = False


def chunks(text: str) -> list[str]:
    result = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > 12000:
            if current:
                result.append(current)
                current = ""
            result.append(line[:12000])
            line = line[12000:]
        if len(current) + len(line) > 12000:
            result.append(current)
            current = ""
        current += line
    if current:
        result.append(current)
    return result


def parse_document(raw: bytes, filename: str, mime: str, reference: str) -> Document:
    if not raw or len(raw) > MAX_BYTES:
        raise EngineError("document_size_invalid", "文档为空或超过 8 MB，未解析。", status_code=422)
    suffix = PurePosixPath(filename).suffix.lower()
    partial = False
    if raw.startswith(b"%PDF-"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise EngineError("document_encrypted", "加密 PDF 需用户提供可读取版本。", status_code=422)
        pages = []
        length = 0
        has_text = False
        for index, page in enumerate(reader.pages):
            if index >= 100 or length >= MAX_TEXT:
                partial = True
                break
            text = page.extract_text() or ""
            has_text = has_text or bool(text.strip())
            pages.append(f"[PDF page {index + 1}]\n{text}\n")
            length += len(pages[-1])
        text = "".join(pages)
        if not has_text:
            raise EngineError("document_ocr_required", "PDF 未取得可读文字；扫描件需 OCR 或提供截图，不能补造正文。", status_code=422)
        mime = "application/pdf"
    elif suffix == ".docx":
        with ZipFile(io.BytesIO(raw)) as archive:
            with archive.open("word/document.xml") as entry:
                xml = entry.read(MAX_BYTES + 1)
            if len(xml) > MAX_BYTES:
                raise EngineError("document_size_invalid", "Word 正文超过解析限制。", status_code=422)
        root = ElementTree.fromstring(xml)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        text = "\n".join("".join(node.itertext()) for node in root.iter(ns + "p"))
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        if suffix not in {"", ".txt", ".md", ".html", ".htm", ".csv"} and not mime.startswith("text/"):
            raise EngineError("document_format_unsupported", "支持 PDF、DOCX、文本、Markdown 和 HTML；未解析其他文件。", status_code=422)
        text = raw.decode("utf-8-sig")
        if "html" in mime or suffix in {".html", ".htm"} or text.lstrip().lower().startswith(("<!doctype html", "<html")):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.body or soup
            text = main.get_text("\n", strip=True)
            mime = "text/html"
        else:
            mime = "text/plain"
    if not text.strip():
        raise EngineError("document_no_text", "没有取得文档正文，未生成替代内容。", status_code=422)
    partial = partial or len(text) > MAX_TEXT
    return Document(text[:MAX_TEXT], raw, mime, reference, partial)


class DocumentReader:
    def __init__(self, *, allow_local: bool = False):
        self.allow_local = allow_local
        self._cache: dict[tuple[str, str], tuple[str, Document]] = {}

    async def read(self, session_id, source, index: int = 0):
        from .session_adapters import Capture, validate_browser_url
        fingerprint = hashlib.sha256(source.input.model_dump_json().encode()).hexdigest()
        key = (session_id, source.source_id)
        cached = self._cache.get(key)
        if cached and cached[0] == fingerprint and source.acquisition_status != "pending":
            document = cached[1]
        elif source.input.content:
            text = source.input.content
            document = Document(text, text.encode("utf-8"), "text/plain", source.input.reference)
        else:
            try:
                if source.input.document_base64:
                    raw = base64.b64decode(source.input.document_base64, validate=True)
                    reference = source.input.reference
                    mime = ""
                    filename = source.input.filename
                else:
                    import httpx
                    reference = source.input.reference
                    raw = b""
                    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                        for _ in range(4):
                            await validate_browser_url(reference, allow_local=self.allow_local)
                            async with client.stream("GET", reference) as response:
                                if response.is_redirect:
                                    from urllib.parse import urljoin
                                    reference = urljoin(reference, response.headers["location"])
                                    continue
                                if response.status_code in {401, 403}:
                                    raise EngineError("document_access_denied", "文档要求访问权限；未绕过登录或付费限制。", status_code=403)
                                response.raise_for_status()
                                mime = response.headers.get("content-type", "").split(";")[0]
                                parts = []
                                size = 0
                                async for part in response.aiter_bytes():
                                    size += len(part)
                                    if size > MAX_BYTES:
                                        raise EngineError("document_size_invalid", "远程文档超过 8 MB，停止读取。", status_code=422)
                                    parts.append(part)
                                raw = b"".join(parts)
                                break
                        else:
                            raise EngineError("document_redirect_limit", "文档重定向过多。", status_code=502)
                    filename = source.input.filename or PurePosixPath(urlparse(reference).path).name
                document = await asyncio.to_thread(parse_document, raw, filename, mime, reference)
            except EngineError:
                raise
            except ImportError as exc:
                raise EngineError("document_dependency_missing", "请安装 requirements-session.txt 的文档解析依赖。", status_code=503) from exc
            except Exception as exc:
                raise EngineError("document_parse_failed", "文档读取或解析失败，未补造内容。", status_code=422) from exc
        self._cache[key] = (fingerprint, document)
        parts = chunks(document.text)
        if index >= len(parts):
            raise EngineError("document_chunk_invalid", "文档分块索引不存在。", status_code=422)
        start = sum(len(part) for part in parts[:index])
        return Capture(
            content=parts[index], state_id=hashlib.sha256((str(index) + parts[index]).encode()).hexdigest()[:24],
            locator={"reference": source.input.reference, "resolved_reference": document.reference,
                     "title": source.input.title, "chunk_index": index, "chunk_count": len(parts),
                     "start_character": start, "end_character": start + len(parts[index]),
                     "start_line": document.text[:start].count("\n") + 1,
                     "end_line": document.text[:start + len(parts[index])].count("\n") + 1,
                     "text_truncated": document.partial, "original_sha256": hashlib.sha256(document.raw).hexdigest()},
            partial=document.partial or len(parts) > 1,
            raw_content=document.text if index == 0 else None,
            original_bytes=document.raw if index == 0 else None,
            original_mime_type=document.mime,
        )
