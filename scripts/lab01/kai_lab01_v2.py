"""Continuidad local del Laboratorio 01 v2, sin motores ni datos de otros grupos."""
from __future__ import annotations

import argparse
from copy import copy
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

from lab01_common_v2 import (_alias, _config, _read_json, _sha, _sheet_paths,
                             _write_json, XML_MAIN, workbook_values)


INDIVIDUAL = "GEM_KAI_LAB01_Plantilla_Individual_v2.xlsx"
GROUP = "GEM_KAI_LAB01_Plantilla_Grupal_v2.xlsx"
SESSION_DATE = "2026-11-11"
STAGES = (("bienvenida", "operacion") + tuple(f"indicador_{i}" for i in range(1, 15))
          + tuple(f"pregunta_{i}" for i in range(1, 7)) + ("decision", "cierre"))
DONE = {"comprendido", "no_disponible"}
SHEET_PROGRESS = "05_KAI_SEGUIMIENTO"
ROW_PROGRESS = {"bienvenida": 7, "operacion": 8, **{f"pregunta_{i}": i + 8 for i in range(1, 7)},
                "decision": 15, "cierre": 16}
STATUS_CELL = {"pendiente": "NO INICIADO", "en_curso": "EN CURSO",
               "requiere_refuerzo": "REQUIERE REFUERZO", "comprendido": "COMPRENDIDO",
               "no_disponible": "NO VERIFICADO"}


def edit_copy(path: Path, changes: dict[str, dict[str, str]]) -> None:
    """Actualiza celdas existentes; preserva las demás partes y fórmulas OOXML."""
    temp = path.with_suffix(".xlsx.tmp")
    with zipfile.ZipFile(path) as source:
        paths = _sheet_paths(source)
        updated = {}
        for sheet_name, cells_to_write in changes.items():
            if sheet_name not in paths:
                raise ValueError(f"Falta hoja {sheet_name}")
            sheet_path = paths[sheet_name]
            root = ET.fromstring(source.read(sheet_path))
            cells = {c.attrib["r"]: c for c in root.iter(f"{{{XML_MAIN}}}c")}
            for address, value in cells_to_write.items():
                if address not in cells:
                    raise ValueError(f"Falta celda formateada {sheet_name}!{address}")
                cell = cells[address]
                formula = cell.find(f"{{{XML_MAIN}}}f")
                if formula is not None:
                    cached = cell.find(f"{{{XML_MAIN}}}v")
                    if cached is None:
                        cached = ET.SubElement(cell, f"{{{XML_MAIN}}}v")
                    cached.text = value
                    cell.attrib["t"] = "str"
                else:
                    for tag in ("v", "is"):
                        existing = cell.find(f"{{{XML_MAIN}}}{tag}")
                        if existing is not None:
                            cell.remove(existing)
                    cell.attrib["t"] = "inlineStr"
                    inline = ET.SubElement(cell, f"{{{XML_MAIN}}}is")
                    text = ET.SubElement(inline, f"{{{XML_MAIN}}}t")
                    text.text = value
                    if value != value.strip():
                        text.attrib["{http://www.w3.org/XML/1998/namespace}space"] = "preserve"
            updated[sheet_path] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(temp, "x") as target:
            for item in source.infolist():
                target.writestr(copy(item), updated.get(item.filename, source.read(item.filename)))
        with zipfile.ZipFile(temp) as target:
            if target.testzip() is not None or target.namelist() != source.namelist():
                raise ValueError("La copia XLSX no pasó integridad ZIP")
            for name in source.namelist():
                if name not in updated and source.read(name) != target.read(name):
                    raise RuntimeError("Se modificó una parte del Excel ajena a la solicitud")
                if name in updated:
                    before = [n.text for n in ET.fromstring(source.read(name)).iter(f"{{{XML_MAIN}}}f")]
                    after = [n.text for n in ET.fromstring(target.read(name)).iter(f"{{{XML_MAIN}}}f")]
                    if before != after:
                        raise RuntimeError("Una fórmula cambió")
    temp.replace(path)
    readback = workbook_values(path, {name: list(values) for name, values in changes.items()})
    if readback != changes:
        raise RuntimeError("No se confirmó la edición de la copia XLSX")


def _first_pending(state: dict) -> str:
    return next((stage for stage in STAGES if state["etapas"][stage] not in DONE), "terminado")


def start(root: Path, alias: str) -> Path:
    config = _config(root)
    alias = _alias(alias)
    template = root / "plantilla" / INDIVIDUAL
    if not template.is_file() or _sha(template) != config.get("individual_sha256"):
        raise ValueError("La plantilla individual v2 no coincide con el maestro de DD")
    base = root / "trabajos" / alias / SESSION_DATE
    if (base / "progreso.json").is_file():
        state = _read_json(base / "progreso.json")
        if state.get("grupo") != config["grupo"] or state.get("alias") != alias:
            raise ValueError("La ficha existente no coincide con grupo y alias")
        if not (base / state["excel"]).is_file():
            raise FileNotFoundError("La ficha existe, pero falta el XLSX individual")
        return base
    archived = root / "cierre" / SESSION_DATE / "individuales" / f"ficha_{alias}.json"
    if archived.is_file() and not base.exists():
        state = _read_json(archived)
        if state.get("version") != 2 or state.get("grupo") != config["grupo"] or state.get("alias") != alias:
            raise ValueError("La ficha archivada no coincide con el alumno y grupo")
        archived_excel = archived.parent / state["excel"]
        if not archived_excel.is_file():
            raise FileNotFoundError("Falta el Excel archivado de la ficha")
        base.mkdir(parents=True)
        shutil.copyfile(archived_excel, base / state["excel"])
        shutil.copyfile(archived, base / "progreso.json")
        if review(base)["identidad_excel"] != "coincide":
            raise ValueError("La identidad del Excel recuperado no coincide")
        return base
    if base.exists() and any(base.iterdir()):
        raise FileExistsError("Ya hay archivos en la sesión; se requiere revisión manual")
    base.mkdir(parents=True, exist_ok=True)
    excel = base / f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_2026-11-11.xlsx"
    shutil.copyfile(template, excel)
    edit_copy(excel, {"00_MI_RUTA": {"C5": alias, "C6": config["grupo"],
                                    "C7": config["operacion"], "C8": SESSION_DATE}})
    if _sha(template) != config["individual_sha256"]:
        raise RuntimeError("Cambió la plantilla maestra durante la copia")
    state = {"version": 2, "grupo": config["grupo"], "operacion": config["operacion"],
             "alias": alias, "fecha": SESSION_DATE, "excel": excel.name,
             "creado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "etapas": {stage: "pendiente" for stage in STAGES},
             "respuestas_breves": {}, "respuestas_por_etapa": {}, "dificultades": {},
             "proxima_actividad": "bienvenida",
             "observaciones_kai": {name: "sin observar" for name in
                                   ("identidad", "claridad", "visor", "correccion", "continuidad")}}
    _write_json(base / "progreso.json", state)
    return base


def record(root: Path, session: Path, stage: str, status: str,
           response: str | None = None, explanation: str | None = None,
           missing: str | None = None, confirmed: bool = False) -> dict:
    config = _config(root)
    session = session.resolve()
    if root.resolve() not in session.parents or "trabajos" not in session.parts:
        raise ValueError("Sesión fuera del paquete grupal")
    state_path = session / "progreso.json"
    state = _read_json(state_path)
    if state.get("version") != 2 or state["grupo"] != config["grupo"]:
        raise ValueError("Ficha de otro grupo o versión")
    if stage not in STAGES or status not in ("pendiente", "en_curso", "requiere_refuerzo", "comprendido", "no_disponible"):
        raise ValueError("Etapa o estado inválido")
    first = _first_pending(state)
    if status != "pendiente" and stage != first:
        raise ValueError(f"Primero queda {first}; no se puede cerrar {stage}")
    if status == "no_disponible" and (not stage.startswith("indicador_") or not missing):
        raise ValueError("NO DISPONIBLE requiere indicador y explicación de la fuente faltante")
    response = response.strip() if response else ""
    explanation = explanation.strip() if explanation else ""
    missing = missing.strip() if missing else ""
    if any(len(value) > 600 for value in (response, explanation, missing)):
        raise ValueError("El registro breve debe caber en 600 caracteres")
    if status == "comprendido" and not response:
        raise ValueError("COMPRENDIDO requiere una respuesta efectivamente recibida")
    excel = session / state["excel"]
    if not excel.is_file():
        raise FileNotFoundError("Falta el XLSX individual")
    if stage.startswith("indicador_") and status == "comprendido":
        row = int(stage.split("_")[1]) + 6
        observed = workbook_values(excel, {"01_DATOS_DEL_VISOR": [f"D{row}", f"E{row}"]})["01_DATOS_DEL_VISOR"]
        if not observed[f"D{row}"] or observed[f"E{row}"] in ("", "PENDIENTE", "NO DISPONIBLE"):
            raise ValueError(f"Registra valor y estado del indicador {stage} en el Excel antes de cerrarlo")
    edits = {}
    if stage in ROW_PROGRESS:
        row = ROW_PROGRESS[stage]
        current = workbook_values(excel, {SHEET_PROGRESS: [f"D{row}", f"E{row}", f"F{row}"]})[SHEET_PROGRESS]
        values = {f"C{row}": STATUS_CELL[status],
                  f"D{row}": response or current[f"D{row}"],
                  f"E{row}": explanation or current[f"E{row}"],
                  f"F{row}": missing or current[f"F{row}"],
                  f"G{row}": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  f"H{row}": "SÍ" if confirmed else "NO"}
        edits[SHEET_PROGRESS] = values
    if stage.startswith("indicador_") and status == "no_disponible":
        row = int(stage.split("_")[1]) + 6
        edits["01_DATOS_DEL_VISOR"] = {f"E{row}": "NO DISPONIBLE"}
    if edits:
        edit_copy(excel, edits)
    state["etapas"][stage] = status
    if response:
        state["respuestas_breves"][stage] = response
        state.setdefault("respuestas_por_etapa", {}).setdefault(stage, []).append(response)
    if missing:
        state["dificultades"][stage] = missing
    state["proxima_actividad"] = _first_pending(state)
    _write_json(state_path, state)
    return _read_json(state_path)


def review(session: Path) -> dict:
    state = _read_json(session / "progreso.json")
    excel = session / state["excel"]
    if not excel.is_file():
        raise FileNotFoundError("Falta el XLSX individual")
    cells = workbook_values(excel, {
        "00_MI_RUTA": ["C5", "C6", "C7", "C8"],
        "01_DATOS_DEL_VISOR": [f"D{i}" for i in range(7, 21)] + [f"E{i}" for i in range(7, 21)],
        "03_SEIS_PREGUNTAS": [f"D{i}" for i in range(7, 13)],
        "04_MI_DECISION": ["C26"],
    })
    ident = cells["00_MI_RUTA"]
    identity_ok = (ident == {"C5": state["alias"], "C6": state["grupo"],
                             "C7": state["operacion"], "C8": state["fecha"]})
    return {"grupo": state["grupo"], "alias": state["alias"], "fecha": state["fecha"],
            "identidad_excel": "coincide" if identity_ok else "incorrecta",
            "indicadores_con_valor": sum(bool(cells["01_DATOS_DEL_VISOR"][f"D{i}"]) for i in range(7, 21)),
            "indicadores_no_disponibles": sum(cells["01_DATOS_DEL_VISOR"][f"E{i}"] == "NO DISPONIBLE"
                                               for i in range(7, 21)),
            "preguntas_con_respuesta": sum(bool(cells["03_SEIS_PREGUNTAS"][f"D{i}"])
                                           for i in range(7, 13)),
            "decision_escrita": bool(cells["04_MI_DECISION"]["C26"]),
            "proxima_actividad": state["proxima_actividad"],
            "limite": "Presencia documental; la comprensión y calificación requieren al profesor."}


def panel(roots: list[Path], output: Path) -> dict:
    rows, warnings = [], []
    for root in roots:
        try:
            config = _config(root)
            for state_path in sorted((root / "trabajos").glob("*/*/progreso.json")):
                state = _read_json(state_path)
                if state.get("version") != 2 or state.get("grupo") != config["grupo"]:
                    raise ValueError(f"Ficha ajena o antigua: {state_path}")
                result = review(state_path.parent)
                rows.append((state, result))
        except (OSError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            warnings.append(f"{root}: {exc}")
    columns = ("Grupo", "Alias", "Fecha", "XLSX", "KPI con valor", "KPI no disponibles",
               "Preguntas escritas", "Decisión", "Siguiente", "Dificultades", "Kai")
    body = []
    for state, result in rows:
        kai = "; ".join(f"{key}: {value}" for key, value in state["observaciones_kai"].items()
                        if value != "sin observar")
        fields = (state["grupo"], state["alias"], state["fecha"], result["identidad_excel"],
                  f"{result['indicadores_con_valor']}/14", result["indicadores_no_disponibles"],
                  f"{result['preguntas_con_respuesta']}/6", "Sí" if result["decision_escrita"] else "No",
                  result["proxima_actividad"], "; ".join(state["dificultades"].values()) or "—", kai or "—")
        body.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in fields) + "</tr>")
    table = "<table><thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in columns) + "</tr></thead><tbody>" + ("".join(body) or '<tr><td colspan="11">Sin sesiones registradas.</td></tr>') + "</tbody></table>"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("<!doctype html><html lang='es'><meta charset='utf-8'><title>Laboratorio 01 · Docente</title>"
                      "<style>body{font:15px system-ui;margin:2rem;color:#183047;background:#f4f7f8}table{border-collapse:collapse;background:white;width:100%}th,td{border:1px solid #d6e2e5;padding:.6rem;text-align:left;vertical-align:top}th{background:#17394d;color:white}</style>"
                      "<h1>Kai Gestión · seguimiento docente v2</h1><p>Solo datos de los XLSX y fichas locales indicados. Sin calificación ni confirmación de entrega remota.</p>"
                      + table + ("<h2>Fuentes omitidas</h2><ul>" + "".join(f"<li>{html.escape(w)}</li>" for w in warnings) + "</ul>" if warnings else "") + "</html>", encoding="utf-8")
    return {"sesiones": len(rows), "fuentes_omitidas": warnings, "panel": str(output)}


def main() -> int:
    p = argparse.ArgumentParser(description="Kai Gestión · Laboratorio 01 v2")
    p.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("iniciar").add_argument("--alias", required=True)
    upd = sub.add_parser("registrar")
    upd.add_argument("--sesion", type=Path, required=True)
    upd.add_argument("--etapa", choices=STAGES, required=True)
    upd.add_argument("--estado", choices=("pendiente", "en_curso", "requiere_refuerzo", "comprendido", "no_disponible"), required=True)
    upd.add_argument("--respuesta")
    upd.add_argument("--explicacion")
    upd.add_argument("--falta")
    upd.add_argument("--confirmado", action="store_true")
    sub.add_parser("revisar").add_argument("--sesion", type=Path, required=True)
    pan = sub.add_parser("panel")
    pan.add_argument("--repos", type=Path, nargs="+", required=True)
    pan.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    try:
        root = args.raiz.resolve()
        if args.cmd == "iniciar":
            print(start(root, args.alias))
        elif args.cmd == "registrar":
            print(json.dumps(record(root, args.sesion, args.etapa, args.estado, args.respuesta,
                                    args.explicacion, args.falta, args.confirmado), ensure_ascii=False, indent=2))
        elif args.cmd == "revisar":
            print(json.dumps(review(args.sesion), ensure_ascii=False, indent=2))
        elif args.cmd == "panel":
            print(json.dumps(panel(args.repos, args.salida), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"LAB01 v2: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
