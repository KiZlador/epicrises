import re

SUBS = str.maketrans(
    {
        "\xa0": " ",
        "\u2009": " ",
        "\u202f": " ",
        "\u200b": "",
        "₂": "2",
        "−": "-",
        "–": "-",
        "—": "-",
    }
)
UNIT_RE1 = re.compile("\\s*[×xхXХ·*]\\s*10\\s*[\\^*]?\\s*[⁰¹²³⁴⁵⁶⁷⁸⁹0-9]+\\s*/\\s*[лlЛL]\\b")
UNIT_RE2 = re.compile("(?<![\\d.,])10\\s*[\\^*]\\s*\\d+\\s*/\\s*[лlЛL]\\b")
HEADER_RE = re.compile("^ ?([А-ЯЁA-Z][^\\n:]{2,80}):[ ]*$", re.M)
SECTION_KEYS = [
    (
        "therapy_discharge",
        "постоянн\\w+\\s+терап|терапи\\w+\\s+при\\s+выписк|рекомендац\\w+\\s+при\\s+выписк|назначени",
    ),
    ("ecg", "экг|электрокардиограф"),
    ("echo", "эхо|эхокардиограф|узи\\s+сердц"),
    ("xray", "рентген|(?<!\\w)рг(?!\\w)"),
    ("ca", "(?<!\\w)каг(?!\\w)|коронарограф|ангиограф"),
    ("lab", "лаборатор|анализ|биохим"),
    ("followup", "повторн|динамик|течение|контрол"),
    ("exam", "объективн|осмотр|статус|status|физикальн"),
    ("diagnosis", "диагноз"),
    ("anamnesis", "анамн?ез|жалоб"),
    ("treatment", "лечени"),
]
NON_EXAM = ("ecg", "echo", "xray", "ca", "lab", "therapy_discharge", "treatment", "followup")


def normalize(raw: str) -> str:
    t = raw.translate(SUBS)
    t = re.sub("\\r\\n?", "\n", t)
    t = re.sub("[ \\t]+", " ", t)
    t = UNIT_RE1.sub("", t)
    t = UNIT_RE2.sub("", t)
    return t


def classify_header(h: str) -> str:
    h = h.lower()
    for name, pat in SECTION_KEYS:
        if re.search(pat, h):
            return name
    return "other"


class Doc:
    def __init__(self, raw: str):
        self.text = normalize(raw)
        self.order: list[tuple[str, str]] = []
        pos, name = (0, "preamble")
        for m in HEADER_RE.finditer(self.text):
            self.order.append((name, self.text[pos : m.start()]))
            name, pos = (classify_header(m.group(1)), m.end())
        self.order.append((name, self.text[pos:]))

    def sec(self, *names: str) -> str:
        return "\n".join((t for n, t in self.order if n in names and t.strip())).strip()

    def without(self, *names: str) -> str:
        return "\n".join((t for n, t in self.order if n not in names)).strip()

    def lines_with(self, pat: str) -> str:
        return "\n".join(line for line in self.text.split("\n") if re.search(pat, line, re.I))

    def main_diag(self) -> str:
        ds = self.sec("diagnosis")
        m = re.search("основн\\w+\\s+диагноз[^\\n:]{0,20}:?\\s*([^\\n]+)", ds or self.text, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(
            "(?:^|\\n)\\s*(?:заключительный\\s+)?диагноз\\s*:\\s*([^\\n]+)", self.text, re.I
        )
        if m:
            return m.group(1).strip()
        return ds.split("\n")[0].strip() if ds else ""
