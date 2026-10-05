import re

from .core import DATE_RE, Hit, clause_span, date_after, ex, norm_date, snippet

KAG_KW = "коронарограф\\w*|(?<!\\w)КАГ(?!\\w)|ангиограф\\w*"
OTHER_ART = "ПМЖВ|ПНА|ПМЖА|(?-i:(?<!\\w)ОА(?!\\w))|огибающ\\w+|(?<!\\w)ПКА(?!\\w)|прав\\w+\\s+коронарн|ствол\\w*|(?<!\\w)ЛКА(?!\\w)|(?<!\\w)ВТК(?!\\w)|диагональн\\w+|(?-i:(?<!\\w)ДВ(?!\\w))|(?<!\\w)ЗНВ(?!\\w)|(?<!\\w)ЗМЖВ(?!\\w)|(?<!\\w)ПЖВ(?!\\w)"
ARTERY = {
    "ca_lad": "ПМЖВ|ПНА|ПМЖА|передн\\w+\\s+межжелудочков\\w+|передн\\w+\\s+нисходящ\\w+",
    "rca": "(?<!\\w)ПКА(?!\\w)|прав\\w+\\s+коронарн\\w+\\s+артери\\w+",
}


def grade_segment(seg: str):
    """-> ('0'|'1'|'2'|None, confidence)"""
    s = seg.lower()
    if re.search(
        "окклюз|полн\\w+\\s+(?:обструкц|закрыт)|тотальн|100\\s*%|не\\s+контрастируется", s
    ):
        return ("2", "high")
    pcts = [float(x.replace(",", ".")) for x in re.findall("(\\d{1,3}(?:[.,]\\d+)?)\\s*%", seg)]
    if pcts:
        v = max(pcts)
        return ("0" if v < 50 else "1" if v < 90 else "2", "high")
    if re.search("субтотальн|критическ\\w+\\s+(?:стеноз|сужени)", s) and (
        not re.search("без\\s+критическ", s)
    ):
        return ("2", "medium")
    if re.search(
        "без\\s+(?:гемодинамическ\\w+\\s+)?(?:значим\\w*\\s+)?(?:стеноз|поражен|сужен)|(?:значим\\w+\\s+)?(?:стеноз\\w*|поражени\\w+|сужени\\w+)\\s+(?:нет|не\\s+(?:выявлен|определя|обнаружен))|гемодинамическ\\w+\\s+значим\\w+\\s+стеноз\\w*\\s+нет|интактн|без\\s+стеноз|неровност",
        s,
    ):
        return ("0", "high")
    if re.search("значим\\w+\\s+(?:стеноз|поражени|сужени)|стеноз|сужени", s):
        return ("1", "low")
    return (None, "none")


@ex("ca_fact")
def _ca_fact(d, key):
    t = d.text
    ca = d.sec("ca")
    refusal = re.search(
        "отказ\\w*[^.;\\n]{0,40}(?:коронарограф|КАГ|ангиограф|инвазивн)|(?:коронарограф\\w*|КАГ|ангиограф\\w*)[^.;\\n]{0,50}отказ",
        t,
        re.I,
    )
    if refusal:
        return Hit("R", snippet(t, refusal.start(), refusal.end()), "regex:ca_refusal")
    notdone = re.search(
        "(?:коронарограф\\w*|КАГ)[^.;\\n]{0,30}не\\s+(?:выполн|проводил|проведен)|не\\s+(?:выполнял\\w+|проводил\\w+)[^.;\\n]{0,20}(?:коронарограф|КАГ)",
        t,
        re.I,
    )
    if notdone:
        return Hit("N", snippet(t, notdone.start(), notdone.end()), "regex:ca_notdone")
    done = re.search(
        "(?:коронарограф\\w*|КАГ)\\s*(?:от\\s+)?\\d|(?:выполнен\\w*|проведен\\w*|проводил\\w*)[^.;\\n]{0,30}(?:коронарограф|КАГ)|(?:коронарограф\\w*|КАГ)[^.;\\n]{0,30}(?:выполнен|проведен)",
        t,
        re.I,
    )
    if done:
        return Hit("Y", snippet(t, done.start(), done.end()), "regex:ca_done")
    if ca and re.search("\\d+\\s*%|ПМЖВ|ПКА|ствол|стеноз|окклюз", ca, re.I):
        return Hit("Y", ca[:80], "section:ca", "medium")
    return Hit("N", "", "default-N")


@ex("ca_date")
def _ca_date(d, key):
    for text in (d.sec("ca"), d.text):
        if not text:
            continue
        r = date_after([KAG_KW], text, gap=25)
        if r:
            return Hit(r[0], r[1], "regex:ca_date")
        for m in re.finditer(DATE_RE + "[^\\n]{0,40}?(?:" + KAG_KW + ")", text, re.I):
            dt = norm_date(*m.groups()[:3])
            if dt:
                return Hit(dt, snippet(text, m.start(), m.end()), "regex:ca_date_before")
    ca = d.sec("ca")
    if ca:
        m = re.match("\\s*" + DATE_RE, ca)
        if m:
            dt = norm_date(*m.groups())
            if dt:
                return Hit(dt, snippet(ca, 0, m.end()), "regex:ca_date_section_start", "medium")
        for m in re.finditer(DATE_RE, ca):
            dt = norm_date(*m.groups())
            if dt:
                try:
                    year = int(dt[-4:])
                    if 1990 <= year <= 2030:
                        return Hit(
                            dt,
                            snippet(ca, m.start(), m.end()),
                            "regex:ca_date_in_section",
                            "medium",
                        )
                except ValueError:
                    pass
    return None


@ex("ca_lad", "rca")
def _artery(d, key):
    for text in (d.sec("ca"), d.text):
        if not text:
            continue
        for m in re.finditer(ARTERY[key], text, re.I):
            s, e = clause_span(text, m.start(), m.end())
            nxt = re.compile(OTHER_ART, re.I).search(text, m.end(), e)
            seg = text[m.end() : nxt.start() if nxt else e]
            val, conf = grade_segment(seg)
            if val is not None:
                return Hit(val, snippet(text, m.start(), m.end() + len(seg)), "regex:artery", conf)
    return None
