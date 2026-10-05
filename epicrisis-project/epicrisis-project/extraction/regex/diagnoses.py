import re

from domain.schema import NA

from .core import EXTRACTORS, Hit, arabic, clause_span, ex, find_pos, lat2cyr_ab, snippet
from .document import Doc

FLAGS = {
    "art_hyper": (
        "гипертоническ\\w+\\s+болезн\\w*|артериальн\\w+\\s+гипертенз\\w*|гипертони\\w+|(?-i:(?<!\\w)(?:АГ|ГБ)(?!\\w))",
        "л[её]гочн|несахарн",
    ),
    "atr_fibril": (
        "фибрилляц\\w+\\s+предсерд\\w*|трепетан\\w+\\s+предсерд\\w*|мерцательн\\w+\\s+аритми\\w*|(?-i:(?<!\\w)ФП(?!\\w))",
        None,
    ),
    "copd": (
        "(?-i:(?<!\\w)ХОБЛ(?!\\w))|хроническ\\w+\\s+обструктивн\\w+\\s+(?:болезн|заболеван)\\w+\\s+л[её]гк\\w*",
        None,
    ),
    "dm": (
        "сахарн\\w+\\s+диабет\\w*|диабет\\w*\\s*[12]\\s*тип|(?-i:(?<!\\w)СД\\s?(?:[12]|II?)(?!\\w))",
        "несахарн|гестационн|предиабет",
    ),
    "tlt": (
        "тромболиз\\w*|тромболитическ\\w+\\s+терапи\\w*|(?-i:(?<!\\w)ТЛТ(?!\\w))|стрептокиназ\\w*|альтеплаз\\w*|тенектеплаз\\w*|проурокиназ\\w*",
        None,
    ),
}


@ex("art_hyper", "atr_fibril", "copd", "dm", "tlt")
def _flags(d: Doc, key):
    pat, skip = FLAGS[key]
    m = find_pos(pat, d.text, skip_ctx=skip)
    if m:
        return Hit("1", snippet(d.text, m.start(), m.end()), f"regex:{key}")
    return Hit("0", "", "absent->0")


@ex("ckd")
def _ckd(d: Doc, key):
    m = find_pos("(?-i:(?<!\\w)ХБП(?!\\w))|хроническ\\w+\\s+болезн\\w+\\s+почек", d.text)
    if not m:
        return None
    s, e = clause_span(d.text, m.start(), m.end())
    tail = d.text[m.end() : e]
    sm = re.match(
        "\\s*(?:стад\\w*\\.?\\s*)?[СC]?\\s*([1-5])\\s*([АБAB])?(?![A-Za-zА-Яа-я0-9])", tail, re.I
    )
    val = "ХБП" + (
        f" {sm.group(1)}{(lat2cyr_ab(sm.group(2)) if sm.group(2) else '')}" if sm else ""
    )
    return Hit(val, snippet(d.text, m.start(), m.end() + 20), "regex:ckd", "high" if sm else "low")


@ex("hf")
def _hf(d: Doc, key):
    m = find_pos(
        "(?-i:(?<!\\w)ХСН(?!\\w))|хроническ\\w+\\s+сердечн\\w+\\s+недостаточност\\w*", d.text
    )
    if not m:
        return None
    s, e = clause_span(d.text, m.start(), m.end())
    tail = d.text[m.end() : e]
    st = re.match(
        "\\s*(?:стад\\w*\\.?\\s*)?(IV|III|II|I|[1-3])\\s*([АБAB])?(?![A-Za-zА-Яа-я0-9])", tail, re.I
    )
    fk = re.search("ФК\\s*(IV|III|II|I|[1-4])(?![A-Za-zА-Яа-я0-9])", tail, re.I)
    parts = [
        "ХСН"
        + (
            f" {arabic(st.group(1))}{(lat2cyr_ab(st.group(2)) if st.group(2) else '')}"
            if st
            else ""
        )
    ]
    if fk:
        parts.append(f"ФК {arabic(fk.group(1))}")
    return Hit(
        ", ".join(parts),
        snippet(d.text, m.start(), m.end() + len(tail)),
        "regex:hf",
        "high" if st or fk else "low",
    )


@ex("diagnosis_icd")
def _icd(d: Doc, key):
    code = "([A-Z]\\d{2}(?:\\.\\d{1,2})?)(?![\\w.]*\\d)"
    for text in (d.main_diag(), d.sec("diagnosis"), d.text):
        if not text:
            continue
        m = re.search("МКБ[^A-Za-z\\n]{0,15}" + code, text, re.I)
        if m:
            return Hit(m.group(1).upper(), snippet(text, m.start(), m.end()), "regex:icd-after-МКБ")
    for text in (d.main_diag(), d.sec("diagnosis"), d.text):
        ms = list(re.finditer("(?<![A-Za-z0-9])" + code, text))
        ms.sort(key=lambda m: (not m.group(1).startswith(("I2", "I5")), m.start()))
        if ms:
            return Hit(
                ms[0].group(1).upper(),
                snippet(text, ms[0].start(), ms[0].end()),
                "regex:icd-any",
                "medium",
            )
    return None


@ex("killip")
def _killip(d: Doc, key):
    m = re.search(
        "(?:killip|киллип|килип)\\s*[:\\-]?\\s*(?:class|класс\\w*)?\\s*(IV|III|II|I|[1-4])(?![A-Za-z0-9])",
        d.text,
        re.I,
    )
    return (
        Hit(arabic(m.group(1)), snippet(d.text, m.start(), m.end()), "regex:killip") if m else None
    )


@ex("type_acs")
def _type_acs(d: Doc, key):
    nst = "без\\s+подъ[её]м\\w*|NSTEMI|ОКС\\s*бп\\s*ST|без\\s+элевац\\w*"
    st = "с\\s+подъ[её]мом|(?<![A-Za-z])STEMI|ОКС\\s*п\\s*ST|с\\s+элевацией"
    for text in (d.main_diag(), d.sec("diagnosis"), d.text):
        if not text:
            continue
        m = re.search(nst, text, re.I)
        if m:
            return Hit("NSTEMI", snippet(text, m.start(), m.end()), "regex:type_acs")
        m = re.search(st, text, re.I)
        if m:
            return Hit("STEMI", snippet(text, m.start(), m.end()), "regex:type_acs")
    icd = EXTRACTORS["diagnosis_icd"](d, "diagnosis_icd")
    if icd and icd.value != NA:
        if icd.value.startswith("I21.4"):
            return Hit("NSTEMI", icd.ev, "icd:I21.4", "medium")
        if re.match("I21\\.[0-3]|I22\\.[0-8]", icd.value):
            return Hit("STEMI", icd.ev, "icd:I21.0-3", "medium")
    return Hit("NA", "", "default-NA", "low")


@ex("mi_localisation")
def _mi_loc(d: Doc, key):
    main = d.main_diag() or d.sec("diagnosis")
    if not re.search("инфаркт|(?<![A-Za-z])I2[12]\\b", main or "", re.I):
        return Hit("N", "", "default-N", "low")
    cands = []
    for pri, code, pat in (
        (0, "L", "заднебоков\\w*|боков\\w*"),
        (1, "A", "передн\\w*|верхушечн\\w*"),
        (2, "I", "задненижн\\w*|нижн\\w*|диафрагмальн\\w*|задн\\w*"),
    ):
        m = re.search(pat, main, re.I)
        if m:
            cands.append((m.start(), pri, code, m))
    if cands:
        cands.sort(key=lambda x: (x[0], x[1]))
        _, _, code, m = cands[0]
        return Hit(code, snippet(main, m.start(), m.end()), "regex:mi_loc")
    icd = EXTRACTORS["diagnosis_icd"](d, "diagnosis_icd")
    if icd and icd.value.startswith("I21.0"):
        return Hit("A", icd.ev, "icd:I21.0", "medium")
    if icd and icd.value.startswith("I21.1"):
        return Hit("I", icd.ev, "icd:I21.1", "medium")
    return Hit("N", main[:80], "default-N (локализация не уточнена)", "low")
