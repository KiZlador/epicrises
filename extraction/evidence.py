import re

from domain.schema import GROUPS, NA

from .regex.document import SUBS, UNIT_RE1, UNIT_RE2


def _indexed_text(raw: str):
    chars, spans = [], []
    for index, char in enumerate(raw):
        for translated in char.translate(SUBS):
            chars.append(translated)
            spans.append((index, index + 1))
    text = "".join(chars)
    for pattern, replacement in (
        (re.compile(r"\r\n?"), "\n"),
        (re.compile(r"[ \t]+"), " "),
        (UNIT_RE1, ""),
        (UNIT_RE2, ""),
        (re.compile(r"\s+"), " "),
    ):
        pieces, positions, cursor = [], [], 0
        for match in pattern.finditer(text):
            pieces.append(text[cursor : match.start()])
            positions.extend(spans[cursor : match.start()])
            if replacement:
                pieces.append(replacement)
                positions.append((spans[match.start()][0], spans[match.end() - 1][1]))
            cursor = match.end()
        pieces.append(text[cursor:])
        positions.extend(spans[cursor:])
        text, spans = "".join(pieces), positions
    return text, spans


def build_evidence(raw: str, result: dict, hits: dict, model=None) -> dict:
    normalized, mapping = _indexed_text(raw)
    evidence = {}
    unresolved = {}
    for group, keys in GROUPS.items():
        evidence[group] = {}
        for key in keys:
            value, hit = result[group][key], hits[key]
            item = {
                "value": value,
                "text": "",
                "start": None,
                "end": None,
                "verified": False,
                "method": "unavailable",
            }
            evidence[group][key] = item
            if value == NA:
                item["method"] = "not-stated"
                continue
            if value == hit.value and hit.ev:
                needle = _indexed_text(hit.ev)[0].strip()
                start = normalized.find(needle) if needle else -1
                if start >= 0 and normalized.find(needle, start + 1) < 0:
                    a, b = mapping[start][0], mapping[start + len(needle) - 1][1]
                    item.update(
                        text=raw[a:b], start=a, end=b, verified=True, method="regex-context"
                    )
            if not item["text"]:
                unresolved[key] = value
    if model and unresolved:
        quotes = model.locate_evidence(raw, unresolved)
        for group in evidence.values():
            for key, item in group.items():
                quote = quotes.get(key)
                if item["text"] or not isinstance(quote, str) or len(quote.strip()) < 5:
                    continue
                start = raw.find(quote)
                if start >= 0 and raw.find(quote, start + 1) < 0:
                    item.update(
                        text=quote,
                        start=start,
                        end=start + len(quote),
                        verified=True,
                        method="model-quote",
                    )
    return evidence


def browser_citations(raw: str, evidence: dict) -> dict:
    citations = {}
    for fields in evidence.values():
        for key, item in fields.items():
            start, end = item.get("start"), item.get("end")
            if (
                isinstance(start, int)
                and isinstance(end, int)
                and 0 <= start < end <= len(raw)
                and raw[start:end] == item.get("text")
            ):
                citations[key] = {
                    "start": len(raw[:start].encode("utf-16-le")) // 2,
                    "end": len(raw[:end].encode("utf-16-le")) // 2,
                }
    return citations
