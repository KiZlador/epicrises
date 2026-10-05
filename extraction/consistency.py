from domain.schema import NA


def check_medical_consistency(hits: dict) -> tuple[list[str], dict]:
    """Выбирает поля для повторного чтения; значения и диагнозы не изменяет."""
    suspicious = set()
    triggered = {}

    def is_reliable(key: str) -> bool:
        """Поле надёжно, если значение не NA и уверенность не низкая."""
        return (
            hits[key].value != NA and hits[key].conf not in ("low", "none") and (not hits[key].warn)
        )

    def try_float(val: str):
        try:
            return float(val.replace(",", "."))
        except (ValueError, AttributeError):
            return None

    if is_reliable("glu") and hits["dm"].value in ("0", "1"):
        glu = try_float(hits["glu"].value)
        if glu is not None:
            if glu > 11.1 and hits["dm"].value == "0":
                suspicious.add("dm")
                triggered.setdefault("rule_1_hyperglycemia_no_dm", []).append("dm")
            if glu < 4.0 and hits["dm"].value == "1":
                suspicious.add("dm")
                triggered.setdefault("rule_1_dm_low_glu", []).append("dm")
    if hits["rg_pc"].value != NA:
        rg_val = hits["rg_pc"].value.lower()
        if any(
            neg in rg_val for neg in ["не получено", "не выявлено", "не обнаружен", "нет данных"]
        ):
            suspicious.add("rg_pc")
            triggered.setdefault("rule_2_rg_pc_negation", []).append("rg_pc")
        elif any(marker in rg_val for marker in ["застой", "отёк", "отек"]):
            if hits["killip"].value == "1":
                suspicious.add("rg_pc")
                triggered.setdefault("rule_2_rg_pc_congestion_killip_1", []).append("rg_pc")
    if hits["ca_fact"].value == "Y" and hits["ca_date"].value == NA:
        suspicious.add("ca_date")
        triggered.setdefault("rule_3_cag_no_date", []).append("ca_date")
    if hits["ca_fact"].value in ("R", "N") and hits["ca_date"].value != NA:
        suspicious.add("ca_date")
        triggered.setdefault("rule_3_cag_not_done_but_date", []).append("ca_date")
    if is_reliable("ca_date") and is_reliable("admission_date") and is_reliable("discharge_date"):
        try:
            from datetime import datetime

            ca_dt = datetime.strptime(hits["ca_date"].value, "%d.%m.%Y")
            adm_dt = datetime.strptime(hits["admission_date"].value, "%d.%m.%Y")
            dis_dt = datetime.strptime(hits["discharge_date"].value, "%d.%m.%Y")
            if not adm_dt <= ca_dt <= dis_dt:
                suspicious.add("ca_date")
                triggered.setdefault("rule_3_ca_date_out_of_range", []).append("ca_date")
        except ValueError:
            pass
    if is_reliable("bp") and hits["art_hyper"].value == "0":
        try:
            sys_bp, dia_bp = map(int, hits["bp"].value.split("/"))
            if sys_bp > 160 or dia_bp > 100:
                suspicious.add("art_hyper")
                triggered.setdefault("rule_4_high_bp_no_hyper", []).append("art_hyper")
        except (ValueError, AttributeError):
            pass
    if is_reliable("ecg_rythm") and hits["atr_fibril"].value == "0":
        if any(
            term in hits["ecg_rythm"].value.lower()
            for term in ["фибрилляц", "мерцательн", "трепетан"]
        ):
            suspicious.add("atr_fibril")
            triggered.setdefault("rule_5_ecg_rythm_afib", []).append("atr_fibril")
    if is_reliable("crea") and hits["ckd"].value == NA:
        crea = try_float(hits["crea"].value)
        if crea is not None and crea > 150:
            suspicious.add("ckd")
            triggered.setdefault("rule_6_high_crea_no_ckd", []).append("ckd")
    if hits["killip"].value in ("3", "4") and hits["hf"].value == NA:
        suspicious.add("hf")
        triggered.setdefault("rule_7_killip_high_no_hf", []).append("hf")
    if is_reliable("echo_ef") and hits["hf"].value == NA:
        ef = try_float(hits["echo_ef"].value)
        if ef is not None and ef < 40:
            suspicious.add("hf")
            triggered.setdefault("rule_7_low_ef_no_hf", []).append("hf")
    if hits["type_acs"].value == "STEMI" and hits["mi_localisation"].value == "N":
        suspicious.add("mi_localisation")
        triggered.setdefault("rule_8_stemi_no_localisation", []).append("mi_localisation")
    if is_reliable("bp") and hits["killip"].value in ("3", "4"):
        try:
            sys_bp = int(hits["bp"].value.split("/")[0])
            if sys_bp > 160:
                suspicious.add("bp")
                triggered.setdefault("rule_9_killip_high_bp_high", []).append("bp")
        except (ValueError, IndexError):
            pass
    if hits["ca_fact"].value != "Y":
        if hits["ca_lad"].value != NA:
            suspicious.add("ca_lad")
            triggered.setdefault("rule_10_cag_not_done_but_lad", []).append("ca_lad")
        if hits["rca"].value != NA:
            suspicious.add("rca")
            triggered.setdefault("rule_10_cag_not_done_but_rca", []).append("rca")
    if hits["ca_fact"].value == "Y":
        if hits["ca_lad"].value == NA:
            suspicious.add("ca_lad")
            triggered.setdefault("rule_10_cag_done_but_no_lad", []).append("ca_lad")
        if hits["rca"].value == NA:
            suspicious.add("rca")
            triggered.setdefault("rule_10_cag_done_but_no_rca", []).append("rca")
    FIELDS_TO_CHECK = [
        "art_hyper",
        "atr_fibril",
        "copd",
        "dm",
        "ckd",
        "hf",
        "mi_localisation",
        "bp",
        "smoking",
        "ca_fact",
        "ca_lad",
        "rca",
        "rg_date",
        "rg_pc",
        "ca_date",
    ]
    for field in FIELDS_TO_CHECK:
        hit = hits[field]
        if hit.conf in ("low",) and hit.value != NA:
            suspicious.add(field)
            triggered.setdefault("rule_12_low_confidence", []).append(field)
        if hit.warn:
            suspicious.add(field)
            triggered.setdefault("rule_12_warnings", []).append(field)
    return (sorted(suspicious), triggered)
