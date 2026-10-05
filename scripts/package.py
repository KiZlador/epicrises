"""Создаёт архив исходников без локальных настроек, весов и результатов обработки."""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {".venv", ".git", ".ruff_cache", "__pycache__", "runtime", "node_modules"}
EXCLUDED_FILES = {".env", ".DS_Store"}


def main():
    destination = ROOT.with_suffix(".zip")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
                continue
            if path.name in EXCLUDED_FILES or path.suffix in {".pyc", ".gguf"}:
                continue
            if relative.parts[0] in {"reports", "test_json"} and path.suffix == ".json":
                continue
            archive.write(path, Path(ROOT.name) / relative)
    print(destination)


if __name__ == "__main__":
    main()
