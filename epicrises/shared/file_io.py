import json
import os
import tempfile
from pathlib import Path


def read_document(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig")


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def documents(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"Каталог документов не найден: {directory}")
    paths = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".md"),
        key=lambda p: p.name.casefold(),
    )
    stems = [p.stem.casefold() for p in paths]
    if len(stems) != len(set(stems)):
        raise ValueError(
            "Имена документов без расширения должны быть уникальными без учёта регистра"
        )
    if not paths:
        raise ValueError(f"В каталоге нет .md: {directory}")
    return paths
