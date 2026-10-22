"""Validation and naming for uploaded Markdown documents and ZIP archives."""

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_BATCH_BYTES = 64 * 1024 * 1024
MAX_DOCUMENTS = 1000
MAX_ARCHIVE_ENTRIES = 5000


@dataclass(frozen=True)
class UploadedDocument:
    name: str
    text: str


@dataclass
class UploadBatch:
    documents: list[UploadedDocument]
    skipped: list[str]


def unique_filename(name: str, used: set[str]) -> str:
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    stem = re.sub(r"[^\w .()\-]", "_", Path(basename).stem).strip(" .")[:100] or "document"
    candidate, index = stem, 1
    while candidate.casefold() in used:
        candidate = f"{stem}_{index}"
        index += 1
    used.add(candidate.casefold())
    return candidate + ".md"


def read_uploads(incoming, existing_names: list[str]) -> UploadBatch:
    """Validate the entire request before writing any documents to storage."""
    documents, skipped = [], []
    used = {Path(name).stem.casefold() for name in existing_names}
    total = 0

    def stage(name, data):
        nonlocal total
        if not name.lower().endswith(".md"):
            skipped.append(name)
            return
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"Документ превышает 2 МиБ: {name}")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Документ должен быть в UTF-8: {name}") from exc
        if not text.strip() or "\x00" in text:
            raise ValueError(f"Пустой или недопустимый текст: {name}")
        total += len(data)
        if total > MAX_BATCH_BYTES or len(documents) + len(existing_names) >= MAX_DOCUMENTS:
            raise ValueError("Превышен лимит: 64 МиБ за загрузку или 1000 документов в сессии")
        documents.append(UploadedDocument(unique_filename(name, used), text))

    for uploaded in incoming:
        name = uploaded.filename or ""
        if not name.lower().endswith(".zip"):
            stage(name, uploaded.stream.read(MAX_DOCUMENT_BYTES + 1))
            continue
        try:
            with zipfile.ZipFile(uploaded.stream) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ARCHIVE_ENTRIES:
                    raise ValueError("Слишком много записей в архиве")
                for entry in entries:
                    if entry.is_dir() or "__MACOSX" in entry.filename.split("/"):
                        continue
                    if not entry.filename.lower().endswith(".md"):
                        skipped.append(entry.filename)
                        continue
                    if entry.file_size > MAX_DOCUMENT_BYTES:
                        raise ValueError(f"Документ превышает 2 МиБ: {entry.filename}")
                    with archive.open(entry) as stream:
                        stage(entry.filename, stream.read(MAX_DOCUMENT_BYTES + 1))
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ValueError("Повреждённый, зашифрованный или неподдерживаемый ZIP") from exc
    return UploadBatch(documents, skipped)
