"""Convert citation spans to the UTF-16 offsets used by the browser."""


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
