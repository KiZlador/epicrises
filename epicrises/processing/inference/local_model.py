import json
import threading

from epicrises.shared.settings import Settings, resolve_path

from ..citations.candidate_lines import candidate_lines
from .prompts import evidence_messages, messages


class LocalModel:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._lock = threading.Lock()

    def ensure_configured(self):
        path = resolve_path(self.settings.model_path)
        if not self.settings.model_path or not path.is_file():
            raise RuntimeError("Укажите MODEL_PATH: путь к существующему GGUF-файлу модели")

    def _load(self):
        if self._model is None:
            self.ensure_configured()
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError("Установите зависимости из requirements-ml.txt") from exc
            self._model = Llama(
                model_path=str(resolve_path(self.settings.model_path)),
                n_ctx=self.settings.context,
                n_gpu_layers=self.settings.gpu_layers,
                n_threads=self.settings.threads,
                n_batch=512,
                verbose=False,
            )

    def _complete(
        self,
        chat_messages: list[dict],
        properties: dict,
        *,
        truncation_error: str,
        contract_error: str,
    ) -> dict:
        with self._lock:
            self._load()
            response = self._model.create_chat_completion(
                messages=chat_messages,
                temperature=0,
                max_tokens=self.settings.max_tokens,
                response_format={
                    "type": "json_object",
                    "schema": {
                        "type": "object",
                        "properties": properties,
                        "required": list(properties),
                        "additionalProperties": False,
                    },
                },
            )
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise RuntimeError(truncation_error)
        payload = json.loads(choice["message"]["content"])
        if not isinstance(payload, dict):
            raise ValueError(contract_error)
        return payload

    def review(self, document: str, fields: list[str], current: dict, analysis: dict) -> dict:
        if not fields:
            return {}
        payload = self._complete(
            messages(document, fields, current, analysis),
            {key: {"type": "string"} for key in fields},
            truncation_error="Ответ модели обрезан: увеличьте MODEL_MAX_TOKENS или MODEL_CONTEXT",
            contract_error="Модель вернула ответ вне JSON-контракта",
        )
        return {key: value for key, value in payload.items() if key in fields}

    def locate_evidence(self, document: str, values: dict) -> dict:
        lines = document.splitlines()
        candidates = candidate_lines(lines, values)
        values = {key: value for key, value in values.items() if candidates[key]}
        if not values:
            return {}
        payload = self._complete(
            evidence_messages(lines, values, candidates),
            {key: {"enum": [None, *candidates[key]]} for key in values},
            truncation_error="Ответ с номерами строк обрезан: увеличьте MODEL_MAX_TOKENS",
            contract_error="Модель вернула цитаты вне JSON-контракта",
        )
        return {
            key: lines[line - 1]
            for key, line in payload.items()
            if key in values and type(line) is int and line in candidates[key]
        }
