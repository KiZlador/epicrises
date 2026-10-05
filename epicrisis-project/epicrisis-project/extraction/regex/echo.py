import re

from .core import NEG_AFTER, Hit, cap, clause_span, ex, negated, pick_num, snippet
from .document import Doc


def echo_texts(d: Doc) -> list[str]:
    return [d.sec("echo"), d.text]


@ex("echo_ef")
def _ef(d, key):
    return pick_num(key, ["(?<!\\w)ФВ(?!\\w)", "фракци\\w+\\s+выброса"], echo_texts(d))


@ex("echo_lvd")
def _lvd(d, key):
    return pick_num(
        key,
        ["(?<!\\w)КДР(?!\\w)", "конечн\\w*[\\s-]*диастолическ\\w+\\s+размер"],
        echo_texts(d),
        gap=20,
    )


@ex("echo_lvd_2")
def _lp(d, key):
    return pick_num(
        key, ["(?-i:(?<!\\w)ЛП(?!\\w))", "левое\\s+предсерди\\w*"], echo_texts(d), gap=15
    )


@ex("echo_mr")
def _mr(d, key):
    deg = "\\s*[:\\-]?\\s*((?:\\d|I{1,3}V?|IV)(?:\\s*-\\s*(?:\\d|I{1,3}))?\\s*(?:ст\\.?|степен\\w*)|(?:незначительн\\w*|минимальн\\w*|умеренн\\w*|выраженн\\w*|небольш\\w*|трив\\w*)(?:\\s+\\w+)?)"
    for text in echo_texts(d):
        for pat in (
            "митральн\\w+\\s+регургитац\\w+",
            "регургитац\\w+\\s+(?:на\\s+)?митральн\\w+\\s+клапан\\w*",
            "(?-i:(?<!\\w)МР(?!\\w))",
        ):
            for m in re.finditer(pat, text, re.I):
                s, e = clause_span(text, m.start(), m.end())
                dm = re.match(deg, text[m.end() : e], re.I)
                is_abbr = pat.startswith("(?-i")
                if is_abbr and (not dm):
                    continue
                if negated(text, m) and (not dm):
                    continue
                base = "Митральная регургитация" if is_abbr else cap(m.group(0))
                val = base + (" " + dm.group(1).strip() if dm else "")
                if (
                    dm
                    and re.search("ст$", val)
                    and (text[m.end() + dm.end() : m.end() + dm.end() + 1] == ".")
                ):
                    val += "."
                return Hit(
                    val,
                    snippet(text, m.start(), m.end() + (dm.end() if dm else 0)),
                    "regex:echo_mr",
                    "high" if dm else "low",
                )
    return None


@ex("echo_zone")
def _zone(d, key):
    pat = "(?:зон\\w*\\s+)?(?:гипокинез\\w*|акинез\\w*|дискинез\\w*)[^.;\\n,]{0,45}"
    for text in echo_texts(d):
        for m in re.finditer(pat, text, re.I):
            if negated(text, m) or NEG_AFTER.match(text[m.end() - 15 : m.end() + 10]):
                continue
            val = re.sub("\\s+(?:и|с|на|в)$", "", m.group(0).strip(" ,.;:"))
            return Hit(cap(val), snippet(text, m.start(), m.end()), "regex:echo_zone")
    return None
