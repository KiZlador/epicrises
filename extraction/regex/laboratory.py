import re

from .core import Hit, clause_span, clean_num, ex, pick_num, snippet

LAB = {
    "ldl": (
        [
            "(?<!\\w)(?:ХС[\\s-]*)?ЛПНП",
            "(?<!\\w)LDL(?:[\\s-]*C)?",
            "холестерин\\w*\\s+липопротеид\\w*\\s+низкой\\s+плотности",
        ],
        None,
    ),
    "tot_chol": (
        [
            "общ\\w*\\.?\\s+холестерин\\w*",
            "холестерин\\w*\\s+общ\\w*",
            "(?-i:(?<!\\w)ОХС?(?!\\w))",
            "(?<!\\w)общ\\.?\\s*ХС",
            "(?<!\\w)холестерин(?!\\w)(?!\\s*-?\\s*(?:ЛП|LDL|HDL|ХС))",
        ],
        None,
    ),
    "crea": (["креатинин\\w*", "creatinine"], "клиренс|СКФ|скорост\\w+\\s+клубочков"),
    "glu": (["глюкоз\\w*", "(?-i:(?<!\\w)GLU(?!\\w))", "сахар\\s+крови"], None),
    "hb": (["гемоглобин\\w*", "(?-i:(?<!\\w)(?:Hb|HGB)(?!\\w))"], None),
    "leucocytes": (["лейкоцит\\w*", "(?-i:(?<!\\w)WBC(?!\\w))"], None),
    "thrombocytes": (["тромбоцит\\w*", "(?-i:(?<!\\w)PLT(?!\\w))"], None),
}


@ex(*LAB.keys())
def _lab(d, key):
    pats, skip = LAB[key]
    return pick_num(key, pats, [d.sec("lab"), d.text], gap=25, skip=skip)


@ex("card_trop")
def _trop(d, key):
    for text in (d.sec("lab"), d.text):
        for m in re.finditer("тропонин\\w*", text, re.I):
            s, e = clause_span(text, m.start(), m.end())
            tail = text[m.end() : e][:80]
            t = tail.lower()
            ev = snippet(text, m.start(), m.end() + len(tail))
            if re.search("отрицательн|не\\s+повышен|не\\s+выявлен|в\\s+пределах\\s+нормы", t):
                return Hit("отрицательный", ev, "regex:trop")
            if re.search("положительн|повышен|выше\\s+нормы|превышен", t):
                return Hit("положительный", ev, "regex:trop")
            nm = re.search("(?<![A-Za-zА-Яа-я])(\\d+(?:[.,]\\d+)?)", tail)
            if nm:
                return Hit(clean_num(nm.group(1)), ev, "regex:trop-num", "medium")
    return None
