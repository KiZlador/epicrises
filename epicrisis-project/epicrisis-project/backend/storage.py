import json
import re
import zipfile
from pathlib import Path

from domain.files import read_document, write_json

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_BATCH_BYTES = 64 * 1024 * 1024
MAX_DOCUMENTS = 1000


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.uploads = root / "uploads"
        self.results = root / "results"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    def document(self, name: str) -> Path:
        if (
            not name
            or name != Path(name).name
            or "/" in name
            or "\\" in name
            or not name.lower().endswith(".md")
        ):
            raise ValueError("Недопустимое имя документа")
        return self.uploads / name

    def result_path(self, name: str, suffix=".json") -> Path:
        return self.results / (self.document(name).stem + suffix)

    def list(self):
        return [
            {"name": path.name, "processed": self.result_path(path.name).is_file()}
            for path in sorted(self.uploads.glob("*.md"), key=lambda p: p.name.casefold())
        ]

    def read_result(self, name: str, suffix=".json"):
        return json.loads(self.result_path(name, suffix).read_text(encoding="utf-8"))

    def raw(self, name: str):
        return read_document(self.document(name))

    def discard_result(self, name: str):
        for suffix in (".json", ".ev.json", ".report.json"):
            self.result_path(name, suffix).unlink(missing_ok=True)

    def save(self, name: str, extraction):
        write_json(self.result_path(name, ".ev.json"), extraction.evidence or {})
        write_json(self.result_path(name, ".report.json"), extraction.report)
        write_json(self.result_path(name), extraction.result)

    def delete(self, name: str):
        self.discard_result(name)
        self.document(name).unlink(missing_ok=True)
        (self.root / "batch-report.json").unlink(missing_ok=True)

    def upload(self, incoming):
        accepted, skipped, pending = [], [], []
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
            if total > MAX_BATCH_BYTES or len(pending) + len(self.list()) >= MAX_DOCUMENTS:
                raise ValueError("Превышен лимит: 64 МиБ за загрузку или 1000 документов в сессии")
            pending.append((name, text))

        for uploaded in incoming:
            name = uploaded.filename or ""
            if name.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(uploaded.stream) as archive:
                        entries = archive.infolist()
                        if len(entries) > 5000:
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
                    raise ValueError(
                        "Повреждённый, зашифрованный или неподдерживаемый ZIP"
                    ) from exc
            else:
                stage(name, uploaded.stream.read(MAX_DOCUMENT_BYTES + 1))
        used = {Path(item["name"]).stem.casefold() for item in self.list()}
        for name, text in pending:
            basename = name.replace("\\", "/").rsplit("/", 1)[-1]
            stem = re.sub(r"[^\w .()\-]", "_", Path(basename).stem).strip(" .")[:100] or "document"
            candidate, index = stem, 1
            while candidate.casefold() in used:
                candidate = f"{stem}_{index}"
                index += 1
            used.add(candidate.casefold())
            filename = candidate + ".md"
            self.document(filename).write_bytes(text.encode("utf-8"))
            accepted.append(filename)
        if accepted:
            (self.root / "batch-report.json").unlink(missing_ok=True)
        return {"accepted": accepted, "skipped": skipped}
