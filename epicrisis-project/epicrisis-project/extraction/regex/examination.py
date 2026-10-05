import re

from domain.schema import NA

from .core import Hit, cap, clause_span, ex, negated, pick_num, snippet
from .document import NON_EXAM, Doc


def exam_texts(d: Doc) -> list[str]:
    return [d.sec("exam"), d.without(*NON_EXAM)]


@ex("height")
def _height(d, key):
    return pick_num(key, ["(?<!\\w)рост(?!\\w)"], exam_texts(d))


@ex("weight")
def _weight(d, key):
    return pick_num(key, ["(?<!\\w)(?:масса\\s+тела|вес|масса)(?!\\w)"], exam_texts(d))


@ex("bmi")
def _bmi(d, key):
    return pick_num(key, ["(?<!\\w)ИМТ(?!\\w)", "индекс\\s+массы\\s+тела"], exam_texts(d), gap=15)


@ex("rr")
def _rr(d, key):
    return pick_num(key, ["(?<!\\w)ЧДД(?!\\w)", "частота\\s+дыхани\\w+"], exam_texts(d), gap=15)


@ex("spo2")
def _spo2(d, key):
    return pick_num(key, ["SpO2|SaO2", "сатурац\\w*"], exam_texts(d), gap=15)


@ex("bp")
def _bp(d, key):
    pat = "(?<!\\w)(?:АД|артериальн\\w+\\s+давлени\\w*|давлени\\w*)(?!\\w)[^\\d\\n]{0,25}?(\\d{2,3})\\s*/\\s*(\\d{2,3})"
    exam = d.sec("exam")
    if exam:
        for m in re.finditer(pat, exam, re.I):
            a, b = (int(m.group(1)), int(m.group(2)))
            if 50 <= a <= 280 and 20 <= b <= 180 and (a > b):
                return Hit(f"{a}/{b}", snippet(exam, m.start(), m.end()), "regex:bp")
    for text in [d.without(*NON_EXAM)]:
        for m in re.finditer(pat, text, re.I):
            a, b = (int(m.group(1)), int(m.group(2)))
            if 50 <= a <= 280 and 20 <= b <= 180 and (a > b):
                return Hit(f"{a}/{b}", snippet(text, m.start(), m.end()), "regex:bp:fallback")
    return None


@ex("bpm")
def _bpm(d, key):
    exam = d.sec("exam")
    if exam:
        r = pick_num(key, ["(?<!\\w)(?:пульс|ЧСС)(?!\\w)(?![^\\d\\n]{0,25}\\d{2,3}\\s/)"], [exam])
        if r and r.value != NA:
            return r
    return pick_num(
        key, ["(?<!\\w)(?:пульс|ЧСС)(?!\\w)(?![^\\d\\n]{0,25}\\d{2,3}\\s/)"], exam_texts(d)
    )


@ex("smoking")
def _smoking(d, key):
    anamnesis_text = d.sec("anamnesis")
    if not anamnesis_text:
        anamnesis_text = d.sec("preamble")
    if not anamnesis_text:
        return None
    pat = re.compile(
        "(?<!\\w)(?:не\\s*)?(?:кур(?:ит|ил\\w*|ение|ящ\\w*|ильщик\\w*)|бросил\\w*\\s+кур\\w*)", re.I
    )
    neg_patterns = [
        "отрицает\\s+кур\\w*",
        "курени[ея]\\s+(?:отсутствует|нет|не\\s+отмечается)",
        "никогда\\s+не\\s+курил\\w*",
    ]
    for neg_pat in neg_patterns:
        m = re.search(neg_pat, anamnesis_text, re.I)
        if m:
            return Hit(
                "не курит", snippet(anamnesis_text, m.start(), m.end()), "regex:smoking-neg", "high"
            )
    best = None
    for m in pat.finditer(anamnesis_text):
        if negated(anamnesis_text, m):
            return Hit(
                "не курит", snippet(anamnesis_text, m.start(), m.end()), "regex:smoking-neg", "high"
            )
        s, e = clause_span(anamnesis_text, m.start(), m.end())
        clause = anamnesis_text[s:e]
        rel = m.start() - s
        if re.search("рекоменд\\w+|совет\\w+|бесед[аы]|разъясн\\w+", clause, re.I):
            continue
        if ":" in clause:
            ci = clause.index(":")
            if ci < rel and (not re.search("кур", clause[:ci], re.I)):
                clause, rel = (clause[ci + 1 :], rel - ci - 1)
        pieces, p = ([], 0)
        for part in clause.split(","):
            pieces.append((p, p + len(part), part))
            p += len(part) + 1
        piece = next((t for a, b, t in pieces if a <= rel <= b), clause)
        cand = (bool(re.search("стаж|индекс|пачко", piece, re.I)), cap(piece), m)
        if best is None or (best[0] and (not cand[0])):
            best = cand
    if not best:
        return None
    return Hit(
        best[1],
        snippet(anamnesis_text, best[2].start(), best[2].end()),
        "regex:smoking",
        "medium" if best[0] else "high",
    )
