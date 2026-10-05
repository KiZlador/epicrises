import re

from .core import Hit, cap, clause_span, ex, snippet
from .document import Doc

DRUGS = {
    "aspirin": "ацетилсалициловая\\s+кислота|ацетилсалициловой\\s+кислоты|(?-i:(?<!\\w)АСК(?!\\w))|аспирин\\w*|кардиомагнил\\w*|тромбо\\s*асс\\w*",
    "2_aag": "тикагрелор\\w*|клопидогрел\\w*|празугрел\\w*|брилинт\\w*|плавикс\\w*|зилт\\w*|эффиент\\w*",
    "bb": "бисопролол\\w*|метопролол\\w*|карведилол\\w*|небиволол\\w*|атенолол\\w*|бетаксолол\\w*|конкор\\w*|эгилок\\w*|бетолок\\w*|кординорм\\w*",
    "ace_ing_sartan": "(?<![А-Яа-яЁё])[А-Яа-яЁё]{3,}прил(?![А-Яа-яЁё])|лозартан\\w*|вальсартан\\w*|валсартан\\w*|кандесартан\\w*|телмисартан\\w*|ирбесартан\\w*|олмесартан\\w*|азилсартан\\w*|сакубитрил\\w*|юперио|энтресто",
    "anticoagulant": "апиксабан\\w*|ривароксабан\\w*|дабигатран\\w*|эдоксабан\\w*|варфарин\\w*|эликвис\\w*|ксарелто\\w*|прадакс\\w*|эноксапарин\\w*|клексан\\w*|надропарин\\w*|фраксипарин\\w*|далтепарин\\w*|фондапаринукс\\w*|арикстра\\w*|гепарин\\w*|бивалирудин\\w*",
    "statin": "аторвастатин\\w*|розувастатин\\w*|симвастатин\\w*|питавастатин\\w*|правастатин\\w*|ловастатин\\w*|флувастатин\\w*|аторис\\w*|крестор\\w*|розукард\\w*|липримар\\w*|торвакард\\w*",
}
DRUG_SKIP = re.compile("аллерг|непереносим|противопоказ|отмен", re.I)
ITEM_END = re.compile("\\n|;|\\s\\d+[.)]\\s")


def _drug_hits(text: str):
    hits = []
    for cls, pat in DRUGS.items():
        for m in re.finditer(pat, text, re.I):
            s, e = clause_span(text, m.start(), m.end())
            if DRUG_SKIP.search(text[s:e]):
                continue
            hits.append((m.start(), m.end(), cls))
    hits.sort()
    return hits


@ex(*DRUGS.keys())
def _drug(d: Doc, key):
    for text in (d.sec("therapy_discharge"), d.text):
        if not text:
            continue
        hits = _drug_hits(text)
        for i, (a, b, cls) in enumerate(hits):
            if cls != key:
                continue
            em = ITEM_END.search(text, b)
            end = em.start() if em else len(text)
            if i + 1 < len(hits) and hits[i + 1][0] < end:
                end = hits[i + 1][0]
            phrase = re.sub("\\s+", " ", text[a:end]).strip(" ,.;:")
            return Hit(cap(phrase[:120]), snippet(text, a, end), f"dict:{key}")
    return None
