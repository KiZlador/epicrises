"""Build downloads from a snapshot of completed results."""

from dataclasses import dataclass

from .formats import XLSX_MIME, build_json, build_xlsx, build_zip


@dataclass(frozen=True)
class Download:
    content: bytes
    mime_type: str
    filename: str


class ExportService:
    def download(self, results: dict, fmt: str, *, single: bool = False) -> Download:
        if fmt not in {"json", "xlsx"}:
            raise ValueError("Неизвестный формат экспорта")
        if not results:
            raise ValueError("Нет обработанных документов")
        if single and len(results) != 1:
            raise ValueError("Для одиночной выгрузки нужен один документ")
        if fmt == "xlsx":
            return Download(build_xlsx(results), XLSX_MIME, "results.xlsx")
        if single:
            return Download(
                build_json(next(iter(results.values()))), "application/json", "result.json"
            )
        return Download(build_zip(results), "application/zip", "results.zip")
