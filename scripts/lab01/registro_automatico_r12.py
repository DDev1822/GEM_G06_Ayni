"""R12: escritura comprobable de respuestas del alumno en su copia individual v2.

No modifica el XLSX maestro, el visor ni datos económicos. Se ejecuta desde el
repositorio individual del grupo. Solo guarda declaraciones efectivamente hechas
por el alumno; la calificación corresponde al docente.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from html import unescape
import json
from pathlib import Path
import re
import sys
import unicodedata

from kai_lab01_v2 import (SESSION_DATE, STAGES, _first_pending, edit_copy,
                          record, review)
from aplicabilidad_historica_cm03 import (STAGES_NO_APLICA, apply_historical_policy)
from lab01_common_v2 import (OPERATIONS, _alias, _config, _read_json, _write_json,
                             workbook_values)

VALID_STATES = {"en_curso", "comprendido", "no_disponible", "requiere_refuerzo", "no_aplica"}
DECISION_CELLS = {
    "alternativas": "C8", "dato1": "C11", "dato2": "C14",
    "costos": "C17", "van_tir": "C20", "riesgo": "C23",
    "recomendacion": "C26", "condicion": "C29",
}
SCENARIO_COLS = {"BASE": "D", "A": "E", "B": "F", "C": "G"}
KPI_ROW = re.compile(
    r'<tr><td>(\d{2})</td><th scope="row">([^<]+)</th>'
    r'<td><strong>([^<]+)</strong></td><td>([^<]+)</td>'
    r'<td>([^<]+)</td><td>([^<]+)</td></tr>'
)
FIXED_NUMERIC = {1, 2, 3, 4, 5, 12}
TOLERANCE = {
    1: Decimal("1"), 2: Decimal("0.05"), 3: Decimal("0.005"),
    4: Decimal("0.05"), 5: Decimal("1000"), 12: Decimal("0"),
    8: Decimal("1"), 9: Decimal("0.01"),
    10: Decimal("0.05"), 11: Decimal("0.05"),
}
UNIT_KIND = {
    1: "t/d", 2: "%", 3: "% Cu", 4: "US$/t procesada",
    5: "US$/mes", 7: "t/d", 8: "US$/t Cu", 9: "MUS$",
    10: "MUS$", 11: "% anual",
    12: "bloques",
}
SOURCE_HINTS = {
    1: ("s04", "estado base", "s11"), 2: ("s04", "estado base", "s11"),
    3: ("s04", "estado base", "s11"), 4: ("s04", "d03", "s11"),
    5: ("s04", "d03", "s11"), 6: ("s04", "s11"),
    7: ("s04", "d02", "s11"), 8: ("t2",),
    9: ("t2",), 10: ("s04", "s11", "t2", "r11"),
    11: ("s04", "s11", "t2", "r11"), 12: ("s12", "d09", "s11"),
    13: ("s11",), 14: ("s11",),
}


def clean(text: str | None, field: str, *, maxlen: int = 1200) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        raise ValueError(f"{field}: se esperaba texto")
    text = text.strip()
    if len(text) > maxlen or "\x00" in text:
        raise ValueError(f"{field}: máximo {maxlen} caracteres y sin caracteres nulos")
    return text


def normal(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).replace("\u2013", "-").replace("\u2014", "-")


def reference_rows(root: Path) -> dict[int, tuple[str, str, str, str]]:
    group = _config(root)["grupo"]
    visor = root / "visor" / f"{group}_S11_S12_VISOR_INTERACTIVO.html"
    try:
        html = visor.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("No se pudo leer la tabla de 14 indicadores del visor R11") from exc
    start = html.find('id="kpi9-guia-excel"')
    end = html.find("</table>", start)
    if start < 0 or end < 0:
        raise ValueError("El visor R11 no contiene la tabla guiada de indicadores")
    matches = KPI_ROW.findall(html[start:end])
    rows = {int(n): tuple(unescape(x).strip() for x in (name, value, unit, source))
            for n, name, value, unit, _, source in matches}
    if len(matches) != 14 or set(rows) != set(range(1, 15)):
        raise ValueError("La tabla R11 no tiene exactamente los 14 indicadores esperados")
    return rows


def historical_records(root: Path) -> dict[str, dict]:
    """Consulta la fuente histórica de esta operación, anclada por SHA."""
    from hashlib import sha256
    config = _config(root)
    path = root / "datos" / f"{config['grupo']}_RESULTADOS_HISTORICOS.json"
    raw = path.read_bytes()
    # El SHA-256 histórico fue fijado sobre CRLF; Git puede entregar LF.
    canonico = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if sha256(canonico).hexdigest() != config.get("historico_sha256"):
        raise ValueError("La fuente histórica cambió respecto del anclaje del grupo")
    data = json.loads(raw)
    if (data.get("grupo"), data.get("operacion"), data.get("excel_t2_sha256")) != (
        config["grupo"], config["operacion"], config.get("historico_t2_sha256")):
        raise ValueError("La fuente histórica no corresponde al T2 de esta operación")
    records = data.get("registros", [])
    lookup = {r["codigo"]: r for r in records}
    if len(records) != len(lookup) or any(r.get("grupo") != config["grupo"] or
            r.get("operacion") != config["operacion"] for r in records):
        raise ValueError("Registros duplicados o procedentes de otra operación")
    return lookup


def number_candidates(raw: str) -> set[Decimal]:
    raw = raw.replace("\u00a0", " ").replace("\u202f", " ").strip()
    if not re.fullmatch(r"-?\d[\d., ]*", raw) or raw.endswith((".", ",")):
        raise ValueError("Se requiere una sola cifra sin operaciones ni cifras adicionales")
    compact = raw.replace(" ", "")
    result: set[Decimal] = set()
    if "." in compact and "," in compact:
        decimal_mark = "." if compact.rfind(".") > compact.rfind(",") else ","
        other = "," if decimal_mark == "." else "."
        result.add(Decimal(compact.replace(other, "").replace(decimal_mark, ".")))
    elif compact.count(".") + compact.count(",") > 1:
        if not re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", compact):
            raise ValueError("Separadores decimales o de miles ambiguos")
        result.add(Decimal(compact.replace(".", "").replace(",", "")))
    elif "." in compact or "," in compact:
        result.add(Decimal(compact.replace(",", ".")))
        if re.fullmatch(r"-?\d{1,3}[.,]\d{3}", compact):
            result.add(Decimal(compact.replace(".", "").replace(",", "")))
    else:
        result.add(Decimal(compact))
    if " " in raw and re.fullmatch(r"-?\d{1,3}(?: \d{3})+", raw):
        result.add(Decimal(raw.replace(" ", "")))
    return result


def number_and_unit(text: str) -> tuple[set[Decimal], str]:
    match = re.fullmatch(r"\s*(-?\d[\d., \u00a0\u202f]*)(.*?)\s*", text)
    if not match:
        raise ValueError("Se requiere una sola cifra del indicador solicitado")
    return number_candidates(match.group(1)), normal(match.group(2)).replace(" ", "")


def monetary_usd(answer: str) -> Decimal:
    """CM-01: una entrada monetaria exige unidad y separadores inequívocos."""
    match = re.fullmatch(r"\s*(-?\d[\d., \u00a0\u202f]*)(.*?)\s*", answer)
    if not match:
        raise ValueError("Indica una sola cifra monetaria y su unidad US$ o MUS$")
    raw = match.group(1).replace("\u00a0", " ").replace("\u202f", " ").strip()
    unit = normal(match.group(2)).replace(" ", "")
    factors = {"us$": Decimal(1), "usd": Decimal(1), "mus$": Decimal(1000000),
               "musd": Decimal(1000000), "millonesdeus$": Decimal(1000000)}
    if unit not in factors:
        raise ValueError("La cifra monetaria requiere unidad explícita US$ o MUS$; no se infiere su escala")
    candidates: set[Decimal] = set()
    if re.fullmatch(r"-?\d+(?:[.,]\d+)?", raw):
        candidates.add(Decimal(raw.replace(",", ".")))
    for grouping, decimal in ((".", ","), (",", "."), (" ", "."), (" ", ",")):
        pattern = r"-?\d{1,3}(?:" + re.escape(grouping) + r"\d{3})+(?:" + re.escape(decimal) + r"\d+)?"
        if re.fullmatch(pattern, raw):
            candidates.add(Decimal(raw.replace(grouping, "").replace(decimal, ".")))
    if len(candidates) != 1:
        raise ValueError("Separadores monetarios ambiguos o inválidos; precisa decimales y miles")
    return candidates.pop() * factors[unit]


def monetary_cell_unit(unit: str) -> Decimal:
    """Factor de la unidad actual del XLSX; nunca aceptar US$/t ni porcentajes."""
    unit = normal(unit).replace(" ", "")
    if unit in ("us$", "usd"):
        return Decimal(1)
    if unit in ("mus$", "musd"):
        return Decimal(1000000)
    raise ValueError("La celda CAPEX/VAN no tiene una unidad monetaria compatible US$/MUS$")


def unit_factor(number: int, unit: str) -> Decimal:
    if not unit:
        return Decimal(1)  # La unidad sigue indicada en la columna C y en la pregunta.
    aliases = {
        "t/d": {"t/d", "toneladas/dia", "toneladaspordia", "toneladasdiarias"},
        "%": {"%", "%cu", "porciento", "porcientocu"},
        "% Cu": {"%", "%cu", "porciento", "porcientocu"},
        "US$/t procesada": {"us$/t", "us$/tprocesada", "usd/t", "usd/tprocesada", "dolares/tonelada"},
        "US$/mes": {"us$/mes", "usd/mes", "dolares/mes"},
        "US$/t Cu": {"us$/tcu", "usd/tcu", "us$/t", "usd/t"},
        "bloques": {"bloque", "bloques"},
        "% anual": {"%", "%anual", "porcientoanual"},
        "MUS$": {"mus$", "musd", "millonesdeus$", "us$", "usd"},
    }
    kind = UNIT_KIND[number]
    if unit not in aliases[kind]:
        raise ValueError(f"Unidad incorrecta para el indicador {number}; corresponde {kind}")
    return Decimal("0.000001") if kind == "MUS$" and unit in {"us$", "usd"} else Decimal(1)


def numeric_match(number: int, answer: str, expected: Decimal) -> bool:
    if number in (9, 10):
        # Ambos resultados de la fuente histórica están en MUS$.
        # Se exige unidad explícita incluso cuando el importe parece correcto.
        return abs(monetary_usd(answer) / Decimal(1000000) - expected) <= TOLERANCE[number]
    candidates, unit = number_and_unit(answer)
    factor = unit_factor(number, unit)
    return any(abs(candidate * factor - expected) <= TOLERANCE[number] for candidate in candidates)


def value_for_template(number: int, answer: str, cell_unit: str) -> str:
    """Normalizar solo cifras de KPI9/10; conservar estados y las filas ajenas."""
    if number not in (9, 10) or not re.match(r"\s*-?\d", answer):
        return answer
    value = monetary_usd(answer) / monetary_cell_unit(cell_unit)
    canonical = format(value, "f")
    return canonical.rstrip("0").rstrip(".") if "." in canonical else canonical


def display_number(number: int, value: str) -> Decimal:
    candidates = number_candidates(value)
    return max(candidates) if number in (5, 12) else min(candidates)


def economic_result(root: Path, number: int, scenario: str) -> tuple[Decimal, str, str]:
    record = historical_records(root).get(f"T2_{'VAN' if number == 10 else 'TIR'}_{scenario}")
    if not record or record["estado_validacion"] not in ("VERIFICADO", "DERIVADO_R11"):
        raise ValueError("Esa alternativa no tiene un resultado económico disponible")
    value = Decimal(str(record["valor"])) * (100 if number == 11 else 1)
    title = (f"{'VAN' if number == 10 else 'TIR'} incremental vs Base · "
             f"{format((Decimal(str(historical_records(root)['T2_TASA_DESCUENTO']['valor'])) * 100).normalize(), 'f') + ' % · ' if number == 10 else ''}{record['periodo']}")
    return value, title, record["estado_validacion"]


def validate_indicator(root: Path, number: int, value: str, source: str,
                       state: str, reason: str, scenario: str | None,
                       period: str) -> None:
    if number in (13, 14):
        raise ValueError("CM-03: NO APLICADO AL CASO HISTÓRICO; no se acepta VER S11, cifras ni interpretación como evidencia histórica")
    if state == "no_aplica":
        raise ValueError("NO APLICA documental se limita a los indicadores 13 y 14")
    rows = reference_rows(root)
    name, published, _, _ = rows[number]
    source_normal = normal(source)
    published_normal = normal(published)
    if number in (9, 10):
        identity = _config(root)
        operation = identity["operacion"]
        if any(normal(other) in source_normal for other in OPERATIONS.values() if other != operation):
            raise ValueError("La procedencia monetaria nombra otra operación; no se registró")
        if any(other.upper() != identity["grupo"] for other in re.findall(r"\bg0[1-6]\b", source_normal)):
            raise ValueError("La procedencia monetaria nombra otro grupo; no se registró")
        alternatives = re.findall(r"alternativa\s+(base|[abc])\b", source_normal)
        if any(other.upper() != scenario for other in alternatives):
            raise ValueError("La procedencia monetaria nombra otra alternativa; no se registró")
    if not source or not any(hint in source_normal for hint in SOURCE_HINTS[number]):
        raise ValueError(f"Indica una fuente R11/S04 pertinente a {name}; no se registró")
    if number in FIXED_NUMERIC and ("t2" in source_normal or "ano" in source_normal):
        raise ValueError("El dato solicitado es Base S04; no uses resultados T2 de otro periodo")
    if number in FIXED_NUMERIC and scenario not in (None, "BASE"):
        raise ValueError("La cifra solicitada corresponde al estado Base, no a A/B/C")
    if state == "no_disponible":
        if number in (8, 9, 10, 11):
            raise ValueError("Esta operación sí tiene este dato en T2/R11; el estado ausente de S04 no describe todo el proyecto")
        if number in FIXED_NUMERIC or number in (6, 7, 13, 14):
            raise ValueError(f"{name} tiene un dato o estado publicado en R11; no marcar NO DISPONIBLE")
        if published_normal not in ("no declarado", "no disponible"):
            raise ValueError(f"{name} no está marcado como ausente en el visor R11")
        if number in (10, 11) and scenario not in (None, "BASE"):
            economic_result(root, number, scenario)
            raise ValueError("La alternativa T2/R11 indicada sí tiene resultado; no marcar NO DISPONIBLE")
        if number in (10, 11) and scenario is None and "s04" not in source_normal:
            raise ValueError("La ausencia publicada corresponde a S04; T2/R11 tiene alternativas concretas")
        return
    if not value:
        raise ValueError("Falta el valor o estado publicado del indicador")
    if number in FIXED_NUMERIC:
        if period and ((number == 1 and "dia" not in normal(period)) or
                       (number == 5 and not any(x in normal(period) for x in ("mes", "30 dias"))) or
                       (number in (2, 3, 4) and "ano" in normal(period))):
            raise ValueError("El periodo declarado no corresponde al indicador Base S04")
        expected = display_number(number, published)
        unit_error = None
        try:
            if numeric_match(number, value, expected):
                return
        except ValueError as exc:
            if "Unidad incorrecta" not in str(exc):
                raise
            unit_error = exc
        try:
            candidates, _ = number_and_unit(value)
        except ValueError:
            raise
        for other in sorted(FIXED_NUMERIC - {number}):
            other_expected = display_number(other, rows[other][1])
            if any(abs(c - other_expected) <= TOLERANCE[other] for c in candidates):
                raise ValueError(f"Ese valor corresponde a {rows[other][0]} ({rows[other][2]}), no a {name}; no se registró")
        if number == 1:
            meta = re.search(r"/\s*([\d.,]+)", rows[7][1])
            if meta and any(abs(c - max(number_candidates(meta.group(1)))) <= Decimal(1) for c in candidates):
                raise ValueError("Ese valor es la meta de planta, no la producción procesada; no se registró")
        if unit_error:
            raise unit_error
        raise ValueError(f"El valor no coincide con {name} del visor R11 para esta operación; no se registró")
    if number == 7:
        if "no determinad" not in normal(value):
            raise ValueError("La capacidad efectiva no está determinada; la meta no debe presentarse como capacidad")
        meta = re.search(r"/\s*([\d.,]+)", published)
        first_digit = re.search(r"\d", value)
        if not meta or not first_digit:
            raise ValueError("La respuesta debe distinguir capacidad no determinada y meta de planta")
        candidates, unit = number_and_unit(value[first_digit.start():])
        unit_factor(7, unit)
        if not any(abs(c - max(number_candidates(meta.group(1)))) <= Decimal(1) for c in candidates):
            raise ValueError("La meta citada no coincide con el visor R11")
        return
    if number == 8:
        if scenario not in (None, "BASE") or "t2" not in source_normal:
            raise ValueError("El precio es un supuesto común del modelo T2, no una cotización ni el estado S04")
        item = historical_records(root)["T2_PRECIO_CU"]
        if not numeric_match(8, value, Decimal(str(item["valor"]))):
            raise ValueError("El precio no coincide con la celda comercial documentada del T2 de esta operación")
        return
    if number == 9:
        if scenario not in ("A", "B", "C") or "t2" not in source_normal or "incremental" not in source_normal:
            raise ValueError("Indica alternativa A/B/C y CAPEX incremental T2 frente a Base")
        if not re.search(r"\bano\s*0\b", normal(period)):
            raise ValueError("El CAPEX incremental solicitado corresponde al año 0")
        item = historical_records(root)[f"T2_CAPEX_INCREMENTAL_{scenario}_ANO0"]
        if not number_and_unit(value)[1]:
            raise ValueError("Indica MUS$ o US$; la ficha individual muestra US$")
        if not numeric_match(9, value, Decimal(str(item["valor"]))):
            raise ValueError("El valor no es el CAPEX incremental de esa alternativa; distingue total e incremental")
        return
    if number in (10, 11) and scenario in ("A", "B", "C"):
        if not any(x in source_normal for x in ("t2", "r11")) or "incremental" not in source_normal:
            raise ValueError("Se requiere resultado incremental T2/R11, no escenario hipotético S04")
        expected, title, evidence_state = economic_result(root, number, scenario)
        horizon = re.search(r"anos\s+0\s*-\s*(\d+)", normal(title))
        if not horizon or not re.search(r"0\s*-\s*" + horizon.group(1) + r"\b", normal(period)):
            raise ValueError(f"Indica el periodo T2/R11 publicado: años 0–{horizon.group(1) if horizon else '?'}")
        rate = re.search(r"(\d+)\s*%", normal(title)) if number == 10 else None
        source_rates = re.findall(r"\b(\d+)\s*%", source_normal) if number == 10 else []
        if number == 10 and (not rate or source_rates != [rate.group(1)]):
            raise ValueError("Indica en la fuente la tasa de VAN publicada en T2/R11")
        if evidence_state == "DERIVADO_R11" and "r11" not in source_normal:
            raise ValueError("Este resultado es derivado R11; identifícalo en la fuente")
        if evidence_state == "DERIVADO_R11" and "verificado" in source_normal:
            raise ValueError("La fuente llama VERIFICADO a un resultado DERIVADO_R11")
        if evidence_state == "VERIFICADO" and "derivado" in source_normal:
            raise ValueError("La fuente llama DERIVADO_R11 a un resultado VERIFICADO")
        if number == 10 and not number_and_unit(value)[1]:
            raise ValueError("Indica MUS$ o US$; la ficha individual muestra US$")
        if not numeric_match(number, value, expected):
            raise ValueError("El valor económico no coincide con esa alternativa y periodo T2/R11")
        return
    if scenario:
        raise ValueError("Ese indicador no admite una alternativa económica numérica sin resultado verificado")
    if number == 6 and ("por determinar" in normal(value) or "aun no determinad" in normal(value)):
        return
    raise ValueError(f"{name} no tiene una cifra única publicada aquí; usa su estado R11 o un resultado T2/R11 verificable")


def context(root: Path, alias: str) -> tuple[Path, dict, Path]:
    config = _config(root)
    alias = _alias(alias)
    folder = root / "trabajos" / alias / SESSION_DATE
    state = _read_json(folder / "progreso.json")
    if state.get("version") != 2 or state.get("alias") != alias or state.get("grupo") != config["grupo"] or state.get("operacion") != config["operacion"] or state.get("fecha") != SESSION_DATE:
        raise ValueError("La ficha no pertenece al alias, fecha y grupo de este repositorio")
    book = folder / state["excel"]
    if not book.is_file() or book.name != f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_{SESSION_DATE}.xlsx":
        raise ValueError("Excel individual incorrecto o inexistente")
    apply_historical_policy(root, folder, edit_copy)
    state = _read_json(folder / "progreso.json")
    return folder, state, book


def cells(book: Path, sheet: str, keys: list[str]) -> dict[str, str]:
    return workbook_values(book, {sheet: keys})[sheet]


def write(book: Path, sheet: str, edits: dict[str, str], *, corregir: bool = False,
          replaceable: tuple[str, ...] = ("", "PENDIENTE", "POR REVISAR", "NO INICIADO")) -> None:
    if not edits:
        return
    old = cells(book, sheet, list(edits))
    for key, value in edits.items():
        if old[key] not in replaceable and old[key] != value and not corregir:
            raise ValueError(f"{sheet}!{key} ya contiene un dato diferente; no se sobrescribió. Para rectificar una respuesta del alumno usa --corregir")
    differences = {key: val for key, val in edits.items() if old[key] != val}
    if differences:
        temp = book.with_suffix(".xlsx.tmp")
        temp_existed = temp.exists()
        try:
            edit_copy(book, {sheet: differences})
        except (OSError, ValueError, RuntimeError):
            # edit_copy deja su temporal si Windows bloquea el reemplazo del XLSX.
            # Retirar solo el temporal creado por esta llamada permite reintentar
            # después sin tocar el Excel ni un temporal preexistente.
            if not temp_existed and temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
            raise
        if cells(book, sheet, list(differences)) != differences:
            raise RuntimeError("La lectura de comprobación no coincide")


def audit_correction(folder: Path, state: dict, *, stage: str, old: dict, new: dict) -> None:
    changed = {k: {"antes": old[k], "despues": v} for k, v in new.items() if old.get(k) != v}
    if not changed:
        return
    updated = _read_json(folder / "progreso.json")
    updated.setdefault("rectificaciones_r12", []).append({
        "etapa": stage, "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "campos": changed,
        "nota": "Cambio explícito solicitado tras nueva respuesta/revisión del alumno; sin reescribir la nota académica.",
    })
    _write_json(folder / "progreso.json", updated)


def check_progress(state: dict, stage: str, corregir: bool = False) -> None:
    pending = _first_pending(state)
    if stage != pending and not (corregir and state["etapas"].get(stage) in ("comprendido", "no_disponible")):
        raise ValueError(f"Etapa fuera de secuencia: corresponde {pending}, no {stage}")


def indicador(root: Path, args) -> dict:
    if args.numero in (13, 14):
        if args.estado != "no_aplica" or any(getattr(args, name, None) for name in
                ("valor", "interpretacion", "fuente", "razon", "periodo", "escenario")):
            raise ValueError("CM-03: 13/14 son NO APLICA documental, sin respuesta; no registrar VER S11 ni COMPRENDIDO")
        folder, state, book = context(root, args.alias)
        stage = f"indicador_{args.numero}"
        if state["etapas"].get(stage) != "no_aplica":
            raise ValueError(f"Antes de NO APLICA corresponde {_first_pending(state)}")
        return {"accion": "no_aplica_documental", "numero": args.numero, "etapa": stage,
                "estado": "no_aplica", "procedencia": state["no_aplicaciones"][stage],
                "proxima_actividad": _first_pending(state), "confirmado_lectura": True}
    if args.estado == "no_aplica":
        raise ValueError("NO APLICA documental se limita a los indicadores 13 y 14")
    folder, state, book = context(root, args.alias)
    number = args.numero
    stage = f"indicador_{number}"
    check_progress(state, stage, args.corregir)
    if state["etapas"].get(stage) in ("comprendido", "no_disponible") and args.estado != state["etapas"][stage]:
        raise ValueError("No se cambia el estado de una etapa ya cerrada mediante una simple rectificación; requiere revisión docente")
    row = number + 6
    key = {part: f"{part}{row}" for part in "DEFG"}
    old = cells(book, "01_DATOS_DEL_VISOR", list(key.values()))
    value = clean(args.valor, "valor", maxlen=400)
    interpretation = clean(args.interpretacion, "interpretación")
    source = clean(args.fuente, "fuente", maxlen=400)
    reason = clean(args.razon, "razón", maxlen=400)
    period = clean(args.periodo, "periodo", maxlen=100)
    if number == 6 and args.estado == "comprendido" and re.sub(r"[^\w]+", " ", normal(interpretation)).strip() in {"por determinar", "aun no determinado", "no determinado", "no determinada"}:
        raise ValueError("POR DETERMINAR es el estado inicial; registra la explicación real de brecha, evidencia e hipótesis pendiente")
    if args.estado == "requiere_refuerzo":
        raise ValueError("Una respuesta incorrecta se explica y guía sin escribirla en Excel")
    scenario = args.escenario
    if number in (9, 10, 11) and args.estado != "no_disponible":
        if scenario and source:
            stated = re.search(r"alternativa\s+([ABC])\b", source, re.IGNORECASE)
            if stated and stated.group(1).upper() != scenario:
                raise ValueError("La fuente nombra otra alternativa económica")
            evidence_state = (economic_result(root, number, scenario)[2] if number in (10, 11)
                              else historical_records(root)[f"T2_CAPEX_INCREMENTAL_{scenario}_ANO0"]["estado_validacion"])
            source = f"{source} · alternativa {scenario} · {period} · {evidence_state}"
        elif not scenario and not value and old[key["D"]]:
            prior_source = old[key["F"]]
            stated = re.search(r"alternativa\s+([ABC])\b", prior_source, re.IGNORECASE)
            stated_period = re.search(r"a[nñ]os\s+0\s*[-–]\s*\d+|a[nñ]o\s+0\b", prior_source, re.IGNORECASE)
            if stated and stated_period:
                scenario = stated.group(1).upper()
                period = stated_period.group()
    checked_value = value or old[key["D"]]
    cell_unit = ""
    if number in (9, 10) and args.estado != "no_disponible" and re.match(r"\s*-?\d", checked_value):
        # Unidad de almacenamiento tomada de la plantilla individual real.
        cell_unit = cells(book, "01_DATOS_DEL_VISOR", [f"C{row}"])[f"C{row}"]
        monetary_cell_unit(cell_unit)
        if not value:
            # Continuación de un turno anterior. Nunca convertir por segunda vez.
            # El registro histórico podía almacenar un importe US$ explícito y CM-01
            # almacena "35000000" en la unidad del encabezado US$.
            # Un D legado con MUS$ bajo C=US$ exige rectificación expresa.
            stored_unit = normal(number_and_unit(checked_value)[1]).replace(" ", "")
            if stored_unit:
                stored_factor = monetary_cell_unit(stored_unit)
                if stored_factor != monetary_cell_unit(cell_unit):
                    raise ValueError("Valor legado con unidad distinta del encabezado; requiere corrección explícita")
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", checked_value):
                checked_value = f"{checked_value} {cell_unit}"
            else:
                raise ValueError("Valor monetario legado ambiguo; requiere corrección explícita")
    validate_indicator(root, number, checked_value, source or old[key["F"]],
                       args.estado, reason, scenario, period)
    stored_value = value_for_template(number, value, cell_unit)
    if value and number in (9, 10) and args.estado != "no_disponible":
        config = _config(root)
        source = (source or old[key["F"]]) + (
            f" · CM-01 {config['grupo']}/{config['operacion']}; entrada: {value}; "
            f"registro: {stored_value} {cell_unit}")
    if args.estado == "no_disponible":
        if value or not reason or not source:
            raise ValueError("NO DISPONIBLE requiere --razon y --fuente, pero no --valor")
        edits = {key["E"]: "NO DISPONIBLE", key["F"]: source, key["G"]: reason}
        if old[key["D"]] and not args.corregir:
            raise ValueError("Existe un valor previo. No declarar NO DISPONIBLE sin corrección explícita")
        if old[key["D"]] and args.corregir:
            edits[key["D"]] = ""
    else:
        edits = {}
        for arg, col in ((stored_value, "D"), (source, "F"), (interpretation, "G")):
            if arg:
                edits[key[col]] = arg
        if args.estado == "comprendido":
            if not args.confirmado:
                raise ValueError("COMPRENDIDO exige --confirmado tras comprobar el razonamiento del alumno")
            upcoming = dict(old, **edits)
            if not all(upcoming[key[col]] for col in ("D", "F", "G")):
                raise ValueError("Para COMPRENDIDO faltan valor, fuente o interpretación del estudiante")
            edits[key["E"]] = "COMPRENDIDO"
        else:
            edits[key["E"]] = "EN CURSO" if args.estado == "en_curso" else "REQUIERE REFUERZO"
        if not (value or interpretation):
            raise ValueError("Se requiere un valor o interpretación realmente recibida del alumno")
    is_prior = state["etapas"].get(stage) in ("comprendido", "no_disponible")
    # Los campos de estado cambian durante la instrucción normal; el guardado
    # parcial no debe exigir --corregir para actualizar EN CURSO a COMPRENDIDO.
    safe_fields = tuple(list(("", "PENDIENTE", "EN CURSO", "REQUIERE REFUERZO")) +
                        (["NO DISPONIBLE", "COMPRENDIDO"] if args.corregir else []))
    # Las fuentes iniciales de la plantilla son orientativas, no declaraciones
    # verificadas del alumno. Permitir precisarlas una vez sin --corregir.
    template_source = (old[key["F"]].startswith(("S04", "S11", "S12", "T2"))
                       and not (old[key["D"]] or old[key["G"]])
                       and state["etapas"][stage] in ("pendiente", "en_curso", "requiere_refuerzo"))
    for cell in (key["D"], key["F"], key["G"]):
        if cell in edits and old[cell] and old[cell] != edits[cell] and not args.corregir:
            if cell == key["F"] and template_source:
                continue
            raise ValueError(f"{cell} cambiaría un dato registrado; usar --corregir")
    allowed = safe_fields + ((old[key["F"]],) if template_source else ())
    write(book, "01_DATOS_DEL_VISOR", edits, corregir=args.corregir, replaceable=allowed)
    if is_prior:
        audit_correction(folder, state, stage=stage, old=old, new=edits)
    else:
        text = (interpretation if args.estado == "comprendido" else value) or value or interpretation or reason
        if args.estado == "comprendido":
            # La operación original conserva la respuesta académica en la ficha
            # y verifica que D/E estén completadas.
            record(root, folder, stage, "comprendido", response=text[:600], confirmed=True)
        elif args.estado == "no_disponible":
            record(root, folder, stage, "no_disponible", response=reason[:600], missing=reason)
        else:
            record(root, folder, stage, args.estado, response=text[:600])
        if args.corregir:
            audit_correction(folder, state, stage=stage, old=old, new=edits)
    return {"accion": "indicador", "numero": number, "etapa": stage,
            "celdas": edits, "proxima_actividad": _read_json(folder/"progreso.json")["proxima_actividad"],
            "confirmado_lectura": True}


def pregunta(root: Path, args) -> dict:
    folder, state, book = context(root, args.alias)
    stage = f"pregunta_{args.numero}"
    check_progress(state, stage, args.corregir)
    if state["etapas"].get(stage)=="comprendido" and args.estado!="comprendido":
        raise ValueError("La corrección de una pregunta ya comprendida no puede retroceder su estado; revisar con docente")
    row = args.numero + 6
    old = cells(book, "03_SEIS_PREGUNTAS", [f"D{row}", f"E{row}", f"F{row}"])
    response = clean(args.respuesta, "respuesta", maxlen=1800)
    example = clean(args.ejemplo, "dato o ejemplo")
    if not response and not old[f"D{row}"]:
        raise ValueError("Debe existir una respuesta realmente proporcionada por el alumno")
    if args.estado == "comprendido" and not args.confirmado:
        raise ValueError("COMPRENDIDO requiere --confirmado tras verificar comprensión")
    edits = {f"F{row}": {"en_curso": "EN PROCESO", "comprendido": "COMPRENDIDO", "requiere_refuerzo": "REQUIERE REFUERZO"}[args.estado]}
    if response:
        edits[f"D{row}"] = response
    if example:
        edits[f"E{row}"] = example
    for k in (f"D{row}", f"E{row}"):
        if k in edits and old[k] and old[k] != edits[k] and not args.corregir:
            raise ValueError(f"{k} ya contiene otra respuesta. Usar --corregir")
    write(book, "03_SEIS_PREGUNTAS", edits, corregir=args.corregir,
          replaceable=("", "POR REVISAR", "EN PROCESO", "REQUIERE REFUERZO"))
    if state["etapas"].get(stage) == "comprendido":
        audit_correction(folder, state, stage=stage, old=old, new=edits)
    else:
        original = (response or old[f"D{row}"])[:600]
        record(root, folder, stage, args.estado, response=original,
               confirmed=args.confirmado)
        if args.corregir:
            audit_correction(folder, state, stage=stage, old=old, new=edits)
    return {"accion": "pregunta", "numero": args.numero, "celdas": edits,
            "proxima_actividad": _read_json(folder/"progreso.json")["proxima_actividad"],
            "confirmado_lectura": True}


def comparacion(root: Path, args) -> dict:
    folder, state, book = context(root, args.alias)
    col = SCENARIO_COLS[args.alternativa]
    addr = f"{col}{args.fila}"
    value = clean(args.valor, "valor comparativo", maxlen=500)
    source = clean(args.fuente, "fuente del resultado", maxlen=400)
    if not value or not source:
        raise ValueError("Debe constar valor y fuente de la comparación expresada por el alumno")
    # Las comparaciones T2/R11 son resultados EXISTENTES, nunca recalcularlas.
    # Registrar la procedencia real por alternativa en H, sin sustituir fuentes.
    old = cells(book, "02_BASE_Y_ABC", [addr, f"H{args.fila}"])
    if old[addr] and old[addr] != value and not args.corregir:
        raise ValueError("La alternativa ya tiene un valor diferente; usar --corregir para rectificar")
    label = f"{args.alternativa}: {source}"
    parts = [part.strip() for part in old[f"H{args.fila}"].split(" | ") if part.strip()]
    found = next((i for i, p in enumerate(parts) if p.startswith(f"{args.alternativa}: ")), None)
    if found is None:
        parts.append(label)
    elif parts[found] != label:
        if not args.corregir:
            raise ValueError("La fuente de la alternativa cambiaría; usar --corregir")
        parts[found] = label
    notes = " | ".join(parts)
    if len(notes) > 1200:
        raise ValueError("Campo H de fuentes demasiado largo")
    edits = {addr: value, f"H{args.fila}": notes}
    write(book, "02_BASE_Y_ABC", edits, corregir=args.corregir or (not old[addr] and bool(old[f"H{args.fila}"])))
    # No marcar etapas comprendidas por simple transcripción.
    if args.corregir:
        audit_correction(folder, state, stage=f"comparacion_{args.fila}_{args.alternativa}", old=old, new=edits)
    return {"accion": "comparacion", "alternativa": args.alternativa, "fila": args.fila,
            "celdas": edits, "confirmado_lectura": True}


def decision(root: Path, args) -> dict:
    folder, state, book = context(root, args.alias)
    target = DECISION_CELLS[args.campo]
    response = clean(args.texto, "respuesta de decisión", maxlen=1800)
    if not response:
        raise ValueError("No se permiten decisiones vacías o escritas por el agente")
    old = cells(book, "04_MI_DECISION", [target])
    if args.cerrar_decision:
        if not args.confirmado:
            raise ValueError("Para cerrar la decisión exige --confirmado")
        if _first_pending(state) != "decision":
            raise ValueError(f"La etapa pendiente es {_first_pending(state)}; no se puede cerrar decisión")
        future = cells(book, "04_MI_DECISION", list(DECISION_CELLS.values()))
        future[target] = response
        missing = [label for label, cell in DECISION_CELLS.items() if not future[cell]]
        if missing:
            raise ValueError(f"Faltan componentes de la decisión: {', '.join(missing)}")
    write(book, "04_MI_DECISION", {target: response}, corregir=args.corregir)
    if args.corregir:
        audit_correction(folder, state, stage=f"decision_{args.campo}", old=old, new={target: response})
    if args.cerrar_decision:
        if not args.confirmado:
            raise ValueError("Para cerrar la decisión exige --confirmado")
        if _first_pending(state) != "decision":
            raise ValueError(f"La etapa pendiente es {_first_pending(state)}; no se puede cerrar decisión")
        all_values = cells(book, "04_MI_DECISION", list(DECISION_CELLS.values()))
        missing = [label for label, cell in DECISION_CELLS.items() if not all_values[cell]]
        if missing:
            raise ValueError(f"Faltan componentes de la decisión: {', '.join(missing)}")
        record(root, folder, "decision", "comprendido", response=all_values["C26"][:600], confirmed=True)
    return {"accion": "decision", "campo": args.campo, "celda": target,
            "cerrada": args.cerrar_decision, "proxima_actividad": _read_json(folder/"progreso.json")["proxima_actividad"],
            "confirmado_lectura": True}


def pausa(root: Path, args, *, finalizar: bool = False) -> dict:
    folder, state, book = context(root, args.alias)
    report = review(folder)
    if finalizar:
        if not args.confirmado:
            raise ValueError("Finalizar la etapa requiere confirmación explícita del alumno")
        if report["proxima_actividad"] != "cierre":
            raise ValueError(f"Aún falta la actividad {report['proxima_actividad']}; usa pausar sin cerrar etapas")
        if (report["indicadores_con_valor"] + report["indicadores_no_disponibles"] + report["indicadores_no_aplica"] < 14
                or report["preguntas_con_respuesta"] < 6 or not report["decision_escrita"]):
            raise ValueError("No es posible cerrar: faltan KPI, preguntas o decisión en Excel")
        record(root, folder, "cierre", "comprendido", response="El alumno confirmó la finalización de su trabajo individual", confirmed=True)
        report = review(folder)
    report["accion"] = "finalizar" if finalizar else "pausar"
    report["nota"] = ("Guardar y cerrar el XLSX; después ejecutar EXPORTAR_MI_TRABAJO.cmd. La finalización no crea ni sube el ZIP."
                     if finalizar else "Progreso local persistido. No equivale a cierre, entrega ni nota. Puede continuar con el mismo alias.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="GEM · R12 escritura automática comprobada de la ficha individual")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("indicador", help="Registra progresivamente KPI 1–14")
    a.add_argument("--alias", required=True)
    a.add_argument("--numero", type=int, required=True, choices=range(1, 15))
    a.add_argument("--valor"); a.add_argument("--interpretacion"); a.add_argument("--fuente")
    a.add_argument("--razon")
    a.add_argument("--escenario", choices=["BASE", "A", "B", "C"])
    a.add_argument("--periodo", help="Periodo del visor; obligatorio para resultados T2/R11")
    a.add_argument("--estado", choices=["en_curso", "comprendido", "no_disponible", "requiere_refuerzo", "no_aplica"], default="en_curso")
    a.add_argument("--confirmado", action="store_true"); a.add_argument("--corregir", action="store_true")
    a = sub.add_parser("pregunta", help="Escribe respuesta propia en hoja 03")
    a.add_argument("--alias", required=True); a.add_argument("--numero", type=int, choices=range(1, 7), required=True)
    a.add_argument("--respuesta"); a.add_argument("--ejemplo")
    a.add_argument("--estado", choices=["en_curso", "comprendido", "requiere_refuerzo"], default="en_curso")
    a.add_argument("--confirmado", action="store_true"); a.add_argument("--corregir", action="store_true")
    a = sub.add_parser("comparacion", help="Escribe comparación T2/R11 o S04 solo desde respuesta real")
    a.add_argument("--alias", required=True); a.add_argument("--fila", type=int, choices=range(7, 15), required=True)
    a.add_argument("--alternativa", choices=list(SCENARIO_COLS), required=True)
    a.add_argument("--valor", required=True); a.add_argument("--fuente", required=True); a.add_argument("--corregir", action="store_true")
    a = sub.add_parser("decision", help="Escribe una parte real de la decisión del alumno")
    a.add_argument("--alias", required=True); a.add_argument("--campo", choices=list(DECISION_CELLS), required=True)
    a.add_argument("--texto", required=True); a.add_argument("--corregir", action="store_true")
    a.add_argument("--cerrar-decision", action="store_true");a.add_argument("--confirmado", action="store_true")
    for name in ("pausar", "finalizar"):
        a = sub.add_parser(name, help="Comprueba avance y guarda sin perder pasos")
        a.add_argument("--alias", required=True)
        if name == "finalizar":a.add_argument("--confirmado", action="store_true")
    args = parser.parse_args()
    try:
        root = args.raiz.resolve()
        if args.cmd == "indicador": out = indicador(root, args)
        elif args.cmd == "pregunta": out = pregunta(root, args)
        elif args.cmd == "comparacion": out = comparacion(root, args)
        elif args.cmd == "decision": out = decision(root, args)
        elif args.cmd == "pausar": out = pausa(root, args)
        else: out = pausa(root, args, finalizar=True)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"LAB01 R12: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
