"""CM-03: hecho documental de no aplicación, sin respuesta ni comprensión ficticia."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil

from lab01_common_v2 import _alias, _config, _read_json, _sha, workbook_values

STAGES_NO_APLICA = ("indicador_13", "indicador_14")
LABEL = "NO APLICADO AL CASO HISTÓRICO"
CELL_STATUS = "NO APLICA"
POLICY = "docs/CM03_HECHO_HISTORICO.md"
POLICY_SHA256 = "8d66922619327e6b21fb3376864c143770047effc0e5ededfe7a37baa38b6519"
JUSTIFICATION = (
    "Hecho documental, no respuesta del estudiante. Mineral y desmonte se recibieron "
    "clasificados en D01; no se calculó ni aplicó una ley de corte al caso original. "
    "S11 es un desarrollo didáctico posterior y complementario.")
EXPLANATION = (
    "El caso original recibió mineral y desmonte previamente clasificados. Por eso, "
    "los indicadores 13 y 14 quedan como NO APLICADO AL CASO HISTÓRICO. "
    "S11 sigue disponible para aprendizaje complementario. Continuamos con las seis "
    "preguntas de integración gerencial.")
JOURNAL = ".cm03_aplicabilidad_pendiente.json"


def source(number: int) -> str:
    return f"CM-03 · KPI {number} · auditoría GEM 12/11/2026 · {POLICY} · SHA-256 {POLICY_SHA256}"


def canonical_cells() -> dict[str, str]:
    return {f"{col}{number+6}": value for number in (13, 14)
            for col, value in (("D", LABEL), ("E", CELL_STATUS),
                               ("F", source(number)), ("G", JUSTIFICATION))}


def is_no_aplica(state: dict, stage: str) -> bool:
    if state["etapas"].get(stage) != "no_aplica":
        return False
    item = state.get("no_aplicaciones", {}).get(stage, {})
    if (stage not in STAGES_NO_APLICA or item.get("indicador") != int(stage.split("_")[1])
            or item.get("estado") != "no_aplica" or item.get("fuente_sha256") != POLICY_SHA256
            or item.get("fuente_documental") != POLICY or item.get("justificacion") != JUSTIFICATION
            or item.get("respuesta_estudiante_requerida") is not False
            or item.get("comprension_evaluada") is not False):
        raise ValueError("NO APLICA requiere indicador 13/14 y procedencia documental CM-03 íntegra")
    return True


def validate_no_aplica(state: dict, book: Path) -> int:
    for stage in state["etapas"]:
        if state["etapas"][stage] == "no_aplica":
            is_no_aplica(state, stage)
    expected = canonical_cells()
    actual = workbook_values(book, {"01_DATOS_DEL_VISOR": list(expected)})["01_DATOS_DEL_VISOR"]
    count = 0
    for stage in STAGES_NO_APLICA:
        row = int(stage.split("_")[1]) + 6
        if is_no_aplica(state, stage):
            if any(actual[f"{col}{row}"] != expected[f"{col}{row}"] for col in "DEFG"):
                raise ValueError("La ficha NO APLICA no coincide con la justificación/fuente del XLSX")
            count += 1
        elif actual[f"E{row}"] == CELL_STATUS or stage in state.get("no_aplicaciones", {}):
            raise ValueError("Registro CM-03 incompleto o contradictorio; reanudar antes de exportar")
    return count


def _atomic_bytes(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".cm03.tmp")
    created = False
    try:
        with temp.open("xb") as output:
            created = True
            output.write(data)
        temp.replace(path)
    finally:
        if created and temp.exists():
            temp.unlink()


def _identity(root: Path, state: dict, book: Path) -> None:
    config = _config(root)
    alias = _alias(state.get("alias", ""))
    name = f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_2026-11-11.xlsx"
    if (state.get("version") != 2 or state.get("grupo") != config["grupo"]
            or state.get("operacion") != config["operacion"] or state.get("fecha") != "2026-11-11"
            or state.get("excel") != name or book.name != name):
        raise ValueError("La política CM-03 corresponde al grupo y sesión v2 de esta ficha")


def _recover(root: Path, session: Path) -> bool:
    journal = session / JOURNAL
    if not journal.is_file():
        return False
    item = _read_json(journal)
    if item.get("schema") != "cm03-documental-transaction/1":
        raise ValueError("Transacción CM-03 desconocida; conservar para revisión")
    before, after = item["state_before"], item["state_after"]
    book = session / after["excel"]
    _identity(root, after, book)
    if before["excel"] != after["excel"]:
        raise ValueError("Transacción CM-03 mezcla identidades")
    original = base64.b64decode(item["book_before_base64"], validate=True)
    desired = base64.b64decode(item["book_after_base64"], validate=True)
    if (sha256(original).hexdigest() != item["book_before_sha256"]
            or sha256(desired).hexdigest() != item["book_after_sha256"]):
        raise ValueError("Respaldo transaccional CM-03 dañado")
    current = _read_json(session / "progreso.json")
    if (current not in (before, after) or _sha(book) not in
            (item["book_before_sha256"], item["book_after_sha256"])):
        raise ValueError("Cambios externos durante CM-03; no se sobrescribe la ficha")
    if _sha(book) != item["book_after_sha256"]:
        _atomic_bytes(book, desired)
    if current != after:
        _atomic_bytes(session / "progreso.json", (json.dumps(after, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
    validate_no_aplica(_read_json(session / "progreso.json"), book)
    journal.unlink()
    return True


def apply_historical_policy(root: Path, session: Path, writer) -> dict:
    """Cierra 13/14 solo después de 1–12. Es idempotente y recuperable."""
    session = session.resolve()
    if root.resolve() not in session.parents or "trabajos" not in session.parts:
        raise ValueError("Sesión CM-03 fuera del paquete")
    if sha256((root / POLICY).read_bytes().replace(b"\r\n", b"\n")).hexdigest() != POLICY_SHA256:
        raise ValueError("La fuente documental CM-03 cambió; no se aplica la política")
    recovered = _recover(root, session)
    state = _read_json(session / "progreso.json")
    book = session / state["excel"]
    _identity(root, state, book)
    if not all(state["etapas"].get(s) in {"comprendido", "no_disponible"}
               for s in ("bienvenida", "operacion", *(f"indicador_{i}" for i in range(1, 13)))):
        return {"aplicados": [], "recuperado": recovered}
    if validate_no_aplica(state, book) == 2:
        return {"aplicados": [], "recuperado": recovered}
    before = deepcopy(state)
    cells = canonical_cells()
    old = workbook_values(book, {"01_DATOS_DEL_VISOR": list(cells)})["01_DATOS_DEL_VISOR"]
    for number in (13, 14):
        stage, row = f"indicador_{number}", number + 6
        if is_no_aplica(state, stage):
            continue
        state.setdefault("no_aplicaciones", {})[stage] = {
            "indicador": number, "estado": "no_aplica", "etiqueta": LABEL,
            "fuente_documental": POLICY, "fuente_sha256": POLICY_SHA256,
            "justificacion": JUSTIFICATION, "actor": "politica_documental_cm03",
            "respuesta_estudiante_requerida": False, "comprension_evaluada": False,
            "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "registro_previo": {"estado": state["etapas"].get(stage),
                               "celdas": {f"{col}{row}": old[f"{col}{row}"] for col in "DEFG"}}}
        state["etapas"][stage] = "no_aplica"
    order = ("bienvenida", "operacion", *(f"indicador_{i}" for i in range(1, 15)),
             *(f"pregunta_{i}" for i in range(1, 7)), "decision", "cierre")
    state["proxima_actividad"] = next((s for s in order if state["etapas"].get(s) not in
                                      {"comprendido", "no_disponible"} and not is_no_aplica(state, s)), "terminado")
    staged = session / ".cm03_aplicabilidad_preparacion.xlsx"
    staged_temp = staged.with_suffix(".xlsx.tmp")
    if staged.exists() or staged_temp.exists():
        raise FileExistsError("Hay una preparación CM-03 previa; conservar para revisión")
    try:
        shutil.copyfile(book, staged)
        writer(staged, {"01_DATOS_DEL_VISOR": cells}, no_aplica_cells=("E19", "E20"))
        validate_no_aplica(state, staged)
        transaction = {"schema": "cm03-documental-transaction/1", "state_before": before,
                       "state_after": state, "book_before_sha256": _sha(book), "book_after_sha256": _sha(staged),
                       "book_before_base64": base64.b64encode(book.read_bytes()).decode("ascii"),
                       "book_after_base64": base64.b64encode(staged.read_bytes()).decode("ascii")}
        _atomic_bytes(session / JOURNAL, (json.dumps(transaction, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
    finally:
        if staged.exists():
            staged.unlink()
        if staged_temp.exists():
            staged_temp.unlink()
    _recover(root, session)
    return {"aplicados": list(STAGES_NO_APLICA), "recuperado": recovered,
            "explicacion": EXPLANATION, "proxima_actividad": state["proxima_actividad"]}
