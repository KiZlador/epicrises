import re

from .core import Hit, ex, find_pos, pick_num, snippet
from .document import Doc


def ecg_text(d: Doc) -> str:
    return d.sec("ecg") or d.lines_with("ЭКГ|электрокардиограф")


@ex("ecg_bpm")
def _ecg_bpm(d, key):
    return pick_num(
        key,
        ["(?<!\\w)ЧСС(?!\\w)", "частота\\s+сердечных\\s+сокращений", "(?<!\\w)пульс(?!\\w)"],
        [ecg_text(d)],
    )


@ex("ecg_rythm")
def _ecg_rythm(d, key):
    text = ecg_text(d)
    adj = "(синусов\\w*|предсердн\\w*|узлов\\w*|идиовентрикулярн\\w*|эктопическ\\w*)"
    for pat in ("ритм\\s*[:\\-]?\\s*" + adj, adj + "\\s+ритм"):
        m = re.search(pat, text, re.I)
        if m:
            v = m.group(1).lower()
            v = "синусовый" if v.startswith("синусов") else v
            return Hit(v, snippet(text, m.start(), m.end()), "regex:ecg_rythm")
    m = find_pos("фибрилляц\\w+\\s+предсерд\\w+|трепетан\\w+\\s+предсерд\\w+", text)
    if m:
        return Hit(
            m.group(0).lower(), snippet(text, m.start(), m.end()), "regex:ecg_rythm", "medium"
        )
    return None


@ex("ecg_elevation")
def _ecg_elev(d, key):
    text = ecg_text(d)
    pat = "элевац\\w+\\s*(?:сегмента\\s*)?(?:ST)?|подъ[её]м\\w*\\s+(?:сегмента\\s+)?ST|ST\\s+(?:элевац\\w+|подъ[её]м\\w*)"
    m = find_pos(pat, text, skip_family=False)
    return (
        Hit("1", snippet(text, m.start(), m.end()), "regex:ecg_elev")
        if m
        else Hit("0", "", "absent->0")
    )


@ex("ecg_avb")
def _ecg_avb(d, key):
    pat = "(?:(?-i:(?<!\\w)АВ(?!\\w))|(?-i:(?<!\\w)AV(?!\\w))|атриовентрикулярн\\w+)[\\s-]*(?:блокад\\w*|блок(?!\\w))"
    for text in (ecg_text(d), d.text):
        m = find_pos(pat, text, skip_family=False)
        if m:
            return Hit("1", snippet(text, m.start(), m.end()), "regex:ecg_avb")
    return Hit("0", "", "absent->0")
