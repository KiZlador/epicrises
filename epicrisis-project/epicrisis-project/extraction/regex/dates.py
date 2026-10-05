import re
from datetime import datetime

from .core import DATE_RE, Hit, date_after, ex, norm_date, snippet
from .document import Doc


def _dates_in_text(d: Doc):
    """Все корректные даты документа, кроме даты рождения (д.р.) и даты оформления; год >= 1990."""
    out = []
    for m in re.finditer(DATE_RE, d.text):
        before = d.text[max(0, m.start() - 25) : m.start()].lower()
        if re.search("д\\.?\\s*р\\.?|рожд|оформлен", before):
            continue
        dt = norm_date(*m.groups())
        if not dt or int(dt[-4:]) < 1990:
            continue
        out.append((datetime.strptime(dt, "%d.%m.%Y"), dt, m))
    return sorted(out, key=lambda x: x[0])


@ex("admission_date")
def _adm(d: Doc, key):
    r = date_after(
        [
            "поступил\\w*",
            "дата\\s+поступлени\\w*",
            "дата\\s+госпитализаци\\w*",
            "госпитализаци\\w*",
            "госпитализирова\\w+",
            "(?<!\\w)с(?=\\s+\\d{1,2}[./]\\d)",
        ],
        d.text,
    )
    if r:
        return Hit(r[0], r[1], "regex:admission")
    ds = _dates_in_text(d)
    if ds:
        return Hit(
            ds[0][1],
            snippet(d.text, ds[0][2].start(), ds[0][2].end()),
            "fallback:earliest_date",
            "low",
        )
    return None


@ex("discharge_date")
def _dis(d: Doc, key):
    r = date_after(
        [
            "выписан\\w*",
            "дата\\s+выписки",
            "выписк\\w*\\s+из\\s+стационара",
            "(?<=\\d{4}\\s)по(?=\\s+\\d{1,2}[./]\\d)",
        ],
        d.text,
    )
    if r:
        return Hit(r[0], r[1], "regex:discharge")
    ds = _dates_in_text(d)
    if ds and ds[-1][1] != ds[0][1]:
        return Hit(
            ds[-1][1],
            snippet(d.text, ds[-1][2].start(), ds[-1][2].end()),
            "fallback:latest_date",
            "low",
        )
    return None
