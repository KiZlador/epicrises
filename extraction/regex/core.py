import re
from dataclasses import dataclass, field
from datetime import datetime

from domain.schema import NA, RANGES


@dataclass
class Hit:
    value: str
    ev: str = ""
    method: str = ""
    conf: str = "high"
    warn: list = field(default_factory=list)


BOUND = re.compile("[;\\n]|(?<=[^\\d])\\.(?=\\s+[А-ЯЁA-Z]|\\s*$)")
NEG_BEFORE = re.compile(
    "(?:(?<!\\w)без(?!\\w)|(?<!\\w)нет(?!\\w)|отсутств\\w*|отрицает|исключ\\w*|(?<!\\w)не\\s+(?:выявлен|отмечен|обнаружен|наблюда|определя|проводил|проводит|выполнял|подтвержд|страда|зарегистрир|регистрир|зафиксир)\\w*)[^.;\\n]{0,25}$",
    re.I,
)
NEG_AFTER = re.compile(
    "^[^.;\\n]{0,25}?(?:(?<!\\w)нет(?!\\w)|отрицает|отсутствует|отсутствуют|исключ\\w*|противопоказан\\w*|(?<!\\w)не\\s+(?:выявлен|отмечен|обнаружен|наблюда|определя|проводил|проводит|выполнял|подтвержд|показан|требовал|планир|страда|зарегистрир|регистрир|зафиксир)\\w*)",
    re.I,
)
FAMILY = re.compile(
    "отец|отца|мать|матер|брат|сестр|наследствен|родственник|родител|дед|бабуш", re.I
)


def snippet(text: str, a: int, b: int, pad: int = 60) -> str:
    return re.sub("\\s+", " ", text[max(0, a - pad) : min(len(text), b + pad)]).strip()


def clause_span(text: str, a: int, b: int):
    s = 0
    for m in BOUND.finditer(text, 0, a):
        s = m.end()
    m2 = BOUND.search(text, b)
    return (s, m2.start() if m2 else len(text))


def negated(text: str, m: re.Match) -> bool:
    s, e = clause_span(text, m.start(), m.end())
    return bool(NEG_BEFORE.search(text[s : m.start()][-40:]) or NEG_AFTER.match(text[m.end() : e]))


def find_pos(pat: str, text: str, skip_family: bool = True, skip_ctx: str | None = None):
    """Находит первое утвердительное упоминание о пациенте."""
    for m in re.finditer(pat, text, re.I):
        if negated(text, m):
            continue
        s, e = clause_span(text, m.start(), m.end())
        ctx = text[s:e]
        if skip_family and FAMILY.search(ctx):
            continue
        if skip_ctx and re.search(skip_ctx, ctx, re.I):
            continue
        return m
    return None


def clean_num(s: str) -> str:
    return s.replace(",", ".").strip()


def in_range(key: str, val: str) -> bool:
    r = RANGES.get(key)
    if not r:
        return True
    try:
        return r[0] <= float(val) <= r[1]
    except ValueError:
        return False


def value_after(pat: str, text: str, gap: int = 25, skip: str | None = None):
    out = []
    for m in re.finditer(pat, text, re.I):
        s, e = clause_span(text, m.start(), m.end())
        if skip and re.search(skip, text[s:e], re.I):
            continue
        tail = text[m.end() : e]
        mm = re.match(rf"[^\d\n]{{0,{gap}}}?(\d+(?:[.,]\d+)?)", tail)
        if mm:
            out.append(
                (m.start(), clean_num(mm.group(1)), (m.end() + mm.start(1), m.end() + mm.end(1)), m)
            )
    return out


def pick_num(key: str, pats: list[str], texts: list[str], gap: int = 25, skip: str | None = None):
    rejected = None
    for text in texts:
        if not text:
            continue
        cands = []
        for p in pats:
            cands += value_after(p, text, gap, skip)
        cands.sort(key=lambda x: x[0])
        for _, val, span, m in cands:
            if in_range(key, val):
                return Hit(val, snippet(text, m.start(), span[1]), f"regex:{key}")
            rejected = rejected or Hit(
                NA,
                snippet(text, m.start(), span[1]),
                "range-reject",
                "low",
                [f"значение {val} вне диапазона {RANGES.get(key)}"],
            )
    return rejected


DATE_RE = "(\\d{1,2})[./](\\d{1,2})[./](\\d{4})"


def norm_date(dd: str, mm: str, yy: str):
    try:
        datetime(int(yy), int(mm), int(dd))
    except ValueError:
        return None
    return f"{int(dd):02d}.{int(mm):02d}.{yy}"


def date_after(pats: list[str], text: str, gap: int = 40):
    for pat in pats:
        for m in re.finditer(pat, text, re.I):
            tail = text[m.end() : m.end() + gap + 12]
            mm = re.match(rf"[^\d\n]{{0,{gap}}}?{DATE_RE}", tail)
            if mm:
                d = norm_date(*mm.groups())
                if d:
                    return (d, snippet(text, m.start(), m.end() + mm.end()))
    return None


def cap(s: str) -> str:
    s = s.strip(" ,.;:")
    return s[:1].upper() + s[1:] if s else s


ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}


def arabic(s: str) -> str:
    return ROMAN.get(s.upper(), s)


def lat2cyr_ab(s: str) -> str:
    return s.upper().replace("A", "А").replace("B", "Б")


EXTRACTORS: dict = {}


def ex(*keys):

    def deco(f):
        for k in keys:
            EXTRACTORS[k] = f
        return f

    return deco
