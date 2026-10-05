import re

from .core import DATE_RE, Hit, cap, clause_span, date_after, ex, negated, norm_date, snippet


@ex("rg_date")
def _rg_date(d, key):
    kw = "рентген\\w*|(?<!\\w)РГ(?!\\w)|(?<!\\w)Rg(?!\\w)|R-?графи\\w*"
    r = date_after([kw], d.text, gap=40)
    if r:
        return Hit(r[0], r[1], "regex:rg_date")
    for m in re.finditer(DATE_RE + "[.,:]?\\s*(?:" + kw + ")", d.text, re.I):
        dt = norm_date(*m.groups()[:3])
        if dt:
            return Hit(dt, snippet(d.text, m.start(), m.end()), "regex:rg_date_before")
    return None


@ex("rg_pc")
def _rg_pc(d, key):
    pat = "венозн\\w+\\s+засто[йяе]\\w*|засто[йяе]\\w*|отёк\\w*\\s+л[её]гк\\w*|отек\\w*\\s+л[её]гк\\w*|интерстициальн\\w+\\s+отёк|интерстициальн\\w+\\s+отек|альвеолярн\\w+\\s+отёк|альвеолярн\\w+\\s+отек|умеренн\\w+\\s+венозн\\w+\\s+засто[йяе]\\w*|выраженн\\w+\\s+венозн\\w+\\s+засто[йяе]\\w*|признак\\w*\\s+(?:венозн\\w+\\s+)?засто[йяе]\\w*"
    NEG_RG = re.compile(
        "не\\s+получен|не\\s+выявлен|не\\s+обнаружен|отсутств\\w+|данных\\s+за\\s+.+не\\s+получено|без\\s+(?:признаков|особенностей)",
        re.I,
    )
    for text in (d.sec("xray"), d.text):
        for m in re.finditer(pat, text, re.I):
            s, e = clause_span(text, m.start(), m.end())
            clause = text[s:e]
            if NEG_RG.search(clause) or negated(text, m):
                continue
            if not re.search("л[её]гк|л[её]гочн|мал\\w*\\s+круг", clause, re.I):
                continue
            val = cap(clause)
            val = re.sub("^(?:Заключение|Описание)\\s*:\\s*", "", val, flags=re.I).strip()
            return Hit(val, snippet(text, m.start(), m.end()), "regex:rg_pc")
    return None
