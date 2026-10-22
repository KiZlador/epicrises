"""Values exchanged between processing stages and their final result."""

from dataclasses import dataclass, field


@dataclass
class Hit:
    value: str
    ev: str = ""
    method: str = ""
    conf: str = "high"
    warn: list = field(default_factory=list)


@dataclass
class Extraction:
    result: dict
    evidence: dict | None
    report: dict
