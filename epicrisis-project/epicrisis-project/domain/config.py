import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


@dataclass(frozen=True)
class Settings:
    model_path: str = ""
    context: int = 8192
    gpu_layers: int = -1
    threads: int = 8
    max_tokens: int = 1600
    llm_enabled: bool = True

    @classmethod
    def from_env(cls):
        return cls(
            model_path=os.getenv("MODEL_PATH", ""),
            context=int(os.getenv("MODEL_CONTEXT", "8192")),
            gpu_layers=int(os.getenv("MODEL_GPU_LAYERS", "-1")),
            threads=int(os.getenv("MODEL_THREADS", "8")),
            max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "1600")),
            llm_enabled=os.getenv("LLM_ENABLED", "true").lower() not in {"0", "false", "no"},
        )
