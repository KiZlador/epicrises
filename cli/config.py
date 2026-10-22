import argparse
from dataclasses import replace

from dotenv import load_dotenv

from domain.config import ROOT, Settings


def add_model_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", help="Путь к GGUF; переопределяет MODEL_PATH")
    parser.add_argument("--regex-only", action="store_true", help="Явный запуск без LLM")


def model_settings(args: argparse.Namespace) -> Settings:
    load_dotenv(ROOT / ".env")
    settings = Settings.from_env()
    if args.model:
        settings = replace(settings, model_path=args.model)
    if args.regex_only:
        settings = replace(settings, llm_enabled=False)
    return settings
