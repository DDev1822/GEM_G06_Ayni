"""Cierre grupal del Laboratorio 01: una entrega, un commit local, ZIP docente.

No se ejecuta en el repositorio maestro. No crea datos ni respuestas de alumnos.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from tempfile import TemporaryDirectory

from lab01_common_v2 import _alias, _config, _read_json, _sha, _sheet_paths, OPERATIONS, XML_MAIN, workbook_values
from kai_lab01_v2 import GROUP, INDIVIDUAL, SESSION_DATE, edit_copy


def _run(args: list[str], root: Path) -> str:
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{args[0]}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def _repo(root: Path, config: dict) -> tuple[str, str]:
    url, branch = config.get("repo_url"), config.get("rama_base")
    if not url or not branch:
        raise ValueError("Faltan repo_url y rama_base del repositorio grupal")
    if not (root / ".git").exists():
        raise ValueError("El paquete no está dentro de un repositorio grupal Git")
    origin = _run(["git", "remote", "get-url", "origin"], root)
    normal = lambda value: value.rstrip("/").removesuffix(".git")
    if normal(origin) != normal(url) or "Gestion_Empresas_Mineras_Repo" in origin:
        raise ValueError("origin no coincide con el repositorio privado del grupo o es el maestro")
    current = _run(["git", "branch", "--show-current"], root)
    if current != branch:
        raise ValueError(f"La rama activa {current} no coincide con rama_base={branch}")
    return origin, branch



def _validate_student(root: Path, state: dict, book: Path) -> str:
    """Comprueba identidad y formato; no evalúa ni completa respuestas académicas."""
    config = _config(root)
    if not isinstance(state, dict) or state.get("version") != 2 or state.get("grupo") != config["grupo"] or state.get("fecha") != SESSION_DATE:
        raise ValueError("Ficha ajena, antigua o de otra fecha")
    alias = _alias(state.get("alias", ""))
    if state.get("operacion") != config["operacion"]:
        raise ValueError("La operación de la ficha no corresponde al grupo")
    name = f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_{SESSION_DATE}.xlsx"
    if state.get("excel") != name or book.name != name:
        raise ValueError("El XLSX no corresponde al alias y grupo declarados")
    master = root / "plantilla" / INDIVIDUAL
    _integrity(book, master, ["00_MI_RUTA", "01_DATOS_DEL_VISOR", "02_BASE_Y_ABC",
                              "03_SEIS_PREGUNTAS", "04_MI_DECISION", "05_KAI_SEGUIMIENTO",
                              "06_FUENTES_Y_LIMITES"])
    vals = workbook_values(book, {"00_MI_RUTA": ["C5", "C6", "C7", "C8"]})["00_MI_RUTA"]
    if vals != {"C5": alias, "C6": config["grupo"], "C7": config["operacion"], "C8": SESSION_DATE}:
        raise ValueError("Identidad del Excel individual incorrecta")
    return alias


def export_student(root: Path, alias: str, output: Path) -> Path:
    """Crea paquete portable para compartir solamente la sesión individual."""
    alias = _alias(alias)
    session = root / "trabajos" / alias / SESSION_DATE
    state_path = session / "progreso.json"
    if not state_path.is_file():
        raise FileNotFoundError("No existe ficha de avance individual para exportar")
    state = _read_json(state_path)
    book = session / state.get("excel", "")
    _validate_student(root, state, book)
    if output.exists():
        raise FileExistsError("Ya existe la exportación. No se sobrescribe")
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": "kai-lab01-individual/1", "grupo": state["grupo"],
               "alias": alias, "fecha": SESSION_DATE, "excel": book.name,
               "sha256": {book.name: _sha(book), "progreso.json": _sha(state_path)},
               "nota": "Respuesta académica no aprobada automáticamente."}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        archive.write(book, book.name)
        archive.write(state_path, "progreso.json")
        archive.writestr("RECIBO_INDIVIDUAL.json", json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return output


def import_student(root: Path, source: Path) -> dict:
    """Importa un ZIP personal sin sobrescribir ni mezclar grupos."""
    if not source.is_file() or source.suffix.lower() != ".zip":
        raise ValueError("Se requiere el ZIP de exportación individual")
    if source.stat().st_size > 35_000_000:
        raise ValueError("ZIP individual demasiado grande")
    with zipfile.ZipFile(source) as archive:
        entries = archive.namelist()
        if archive.testzip() is not None or "RECIBO_INDIVIDUAL.json" not in entries or "progreso.json" not in entries:
            raise ValueError("ZIP individual incompleto o dañado")
        if len(entries) != 3 or any("/" in name or "\\" in name or name.startswith(".") for name in entries):
            raise ValueError("La exportación individual tiene entradas inesperadas")
        if any(archive.getinfo(name).file_size > 30_000_000 for name in entries):
            raise ValueError("Un archivo individual excede el límite")
        receipt = json.loads(archive.read("RECIBO_INDIVIDUAL.json"))
        state_bytes = archive.read("progreso.json")
        state = json.loads(state_bytes)
        alias = _alias(state.get("alias", ""))
        book_name = state.get("excel", "")
        config = _config(root)
        if state.get("grupo") != config["grupo"]:
            raise ValueError("ZIP individual pertenece a otro grupo")
        if book_name != f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_{SESSION_DATE}.xlsx":
            raise ValueError("Nombre individual inesperado o ruta insegura")
        if (receipt.get("schema") != "kai-lab01-individual/1" or receipt.get("grupo") != config["grupo"]
                or receipt.get("alias") != alias or receipt.get("fecha") != SESSION_DATE
                or receipt.get("excel") != book_name or book_name not in entries):
            raise ValueError("El recibo no coincide con la ficha o el grupo")
        book_bytes = archive.read(book_name)
        if receipt.get("sha256") != {book_name: sha256(book_bytes).hexdigest(),
                                     "progreso.json": sha256(state_bytes).hexdigest()}:
            raise ValueError("SHA-256 de la exportación individual no coincide")
    dest = root / "trabajos" / alias / SESSION_DATE
    if dest.exists():
        raise FileExistsError(f"La sesión de {alias} ya existe. No se sobrescribe")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="lab01_import_", dir=dest.parent) as tmp:
        staged = Path(tmp)
        (staged / book_name).write_bytes(book_bytes)
        (staged / "progreso.json").write_bytes(state_bytes)
        _validate_student(root, state, staged / book_name)
        staged.rename(dest)
    return {"grupo": config["grupo"], "alias": alias, "estado": "IMPORTACION_VERIFICADA",
            "sesion": str(dest)}


def incorporate(root: Path) -> dict:
    """Añade estudiantes recién importados a un cierre preparado, sin sobrescribir."""
    config = _config(root)
    closure = root / "cierre" / SESSION_DATE
    target = closure / "individuales"
    if not target.is_dir():
        raise FileNotFoundError("Primero prepara el cierre grupal")
    added = []
    for state_path in sorted((root / "trabajos").glob(f"*/{SESSION_DATE}/progreso.json")):
        state = _read_json(state_path)
        book = state_path.parent / state.get("excel", "")
        alias = _validate_student(root, state, book)
        target_book = target / book.name
        target_state = target / f"ficha_{alias}.json"
        if target_book.exists() or target_state.exists():
            if (not target_book.exists() or not target_state.exists() or
                    _sha(target_book) != _sha(book) or _sha(target_state) != _sha(state_path)):
                raise FileExistsError(f"El cierre contiene una versión distinta de {alias}; revisar manualmente")
            continue
        shutil.copyfile(book, target_book)
        shutil.copyfile(state_path, target_state)
        added.append(alias)
    return {"grupo": config["grupo"], "agregados": added}


def prepare(root: Path) -> Path:
    config = _config(root)
    template = root / "plantilla" / GROUP
    if not template.is_file() or _sha(template) != config.get("grupal_sha256"):
        raise ValueError("La plantilla grupal v2 no coincide con el maestro de DD")
    closure = root / "cierre" / SESSION_DATE
    if closure.exists():
        raise FileExistsError("Ya existe el cierre de esta sesión; no se sobrescribe")
    (closure / "individuales").mkdir(parents=True)
    for folder in ("manuscrito", "retroalimentacion", "evidencia_visor"):
        (closure / folder).mkdir()
    group_book = closure / f"GEM_KAI_LAB01_{config['grupo']}_Grupal_{SESSION_DATE}.xlsx"
    shutil.copyfile(template, group_book)
    edit_copy(group_book, {"00_EQUIPO": {"D5": config["grupo"], "D6": config["operacion"],
                                          "D7": SESSION_DATE}})
    incorporate(root)
    (closure / "LEEME_CIERRE.md").write_text(
        "# Cierre grupal · Laboratorio 01\n\n"
        "El representante completa el Excel grupal y reúne los Excel individuales. "
        "Coloca una foto/PDF de las seis respuestas manuscritas y la decisión en `manuscrito/`; "
        "retroalimentación formativa basada en conversación real en `retroalimentacion/`; "
        "y capturas pertinentes del visor de este grupo en `evidencia_visor/`. "
        "Revisa legibilidad y participación antes de validar. "
        "El script verifica presencia y estructura, no aprueba académicamente las respuestas.\n",
        encoding="utf-8")
    return closure


def _integrity(book: Path, master: Path, expected_sheets: list[str]) -> None:
    with zipfile.ZipFile(book) as actual, zipfile.ZipFile(master) as original:
        if actual.testzip() is not None or original.testzip() is not None:
            raise ValueError(f"XLSX dañado: {book.name}")
        actual_paths, original_paths = _sheet_paths(actual), _sheet_paths(original)
        if list(actual_paths) != expected_sheets or list(original_paths) != expected_sheets:
            raise ValueError(f"Hojas faltantes o cambiadas: {book.name}")
        for sheet in expected_sheets:
            before = [node.text for node in ET.fromstring(original.read(original_paths[sheet])).iter(f"{{{XML_MAIN}}}f")]
            after = [node.text for node in ET.fromstring(actual.read(actual_paths[sheet])).iter(f"{{{XML_MAIN}}}f")]
            if before != after:
                raise ValueError(f"Fórmulas cambiadas en {book.name}: {sheet}")


def verify(root: Path, *, strict: bool = True) -> dict:
    config = _config(root)
    group = config["grupo"]
    closure = root / "cierre" / SESSION_DATE
    if not closure.is_dir():
        raise FileNotFoundError("Aún no se preparó el cierre grupal")
    other_groups = [key for key in OPERATIONS if key != group]
    for path in closure.rglob("*"):
        if path.is_file() and any(re.search(rf"(?<![A-Za-z0-9]){key}(?![A-Za-z0-9])", path.name) for key in other_groups):
            raise ValueError(f"Archivo de otro grupo en el cierre: {path.name}")
    group_book = closure / f"GEM_KAI_LAB01_{group}_Grupal_{SESSION_DATE}.xlsx"
    if not group_book.is_file():
        raise FileNotFoundError("Falta el Excel grupal")
    master_group = root / "plantilla" / GROUP
    master_ind = root / "plantilla" / INDIVIDUAL
    _integrity(group_book, master_group, ["00_EQUIPO", "01_KPI_BASE_ABC", "02_6_RESPUESTAS",
                                          "03_DECISION_FINAL", "04_HOJA_A_MANO", "05_ENTREGA_COMMIT",
                                          "06_PROFESOR", "07_FUENTES"])
    group_values = workbook_values(group_book, {
        "00_EQUIPO": ["D5", "D6", "D7"],
        "02_6_RESPUESTAS": [f"D{i}" for i in range(7, 13)],
        "03_DECISION_FINAL": ["D11", "D14", "D26", "D29"],
    })
    if group_values["00_EQUIPO"] != {"D5": group, "D6": config["operacion"], "D7": SESSION_DATE}:
        raise ValueError("Identidad grupal incorrecta")
    missing = []
    group_count = sum(bool(value) for value in group_values["02_6_RESPUESTAS"].values())
    if group_count < 6:
        missing.append(f"Faltan respuestas consensuadas grupales: {6-group_count}/6")
    decision = group_values["03_DECISION_FINAL"]
    for key in ("D11", "D14", "D26", "D29"):
        if not decision[key]:
            missing.append(f"Falta sustento o decisión grupal en {key}")
    individuals = sorted((closure / "individuales").glob("*.xlsx"))
    if not individuals:
        missing.append("No hay Excel individuales")
    aliases = set()
    for book in individuals:
        _integrity(book, master_ind, ["00_MI_RUTA", "01_DATOS_DEL_VISOR", "02_BASE_Y_ABC",
                                      "03_SEIS_PREGUNTAS", "04_MI_DECISION", "05_KAI_SEGUIMIENTO",
                                      "06_FUENTES_Y_LIMITES"])
        values = workbook_values(book, {
            "00_MI_RUTA": ["C5", "C6", "C7", "C8"],
            "03_SEIS_PREGUNTAS": [f"D{i}" for i in range(7, 13)],
            "04_MI_DECISION": ["C26"],
        })
        identity = values["00_MI_RUTA"]
        if (not identity["C5"] or identity["C5"] in aliases or identity["C6"] != group
                or identity["C7"] != config["operacion"] or identity["C8"] != SESSION_DATE):
            raise ValueError(f"Identidad incorrecta o alias duplicado: {book.name}")
        aliases.add(identity["C5"])
        archived = closure / "individuales" / f"ficha_{identity['C5']}.json"
        if not archived.is_file():
            missing.append(f"Falta ficha de continuidad de {identity['C5']}")
        else:
            state = _read_json(archived)
            if state.get("grupo") != group or state.get("alias") != identity["C5"] or state.get("excel") != book.name:
                raise ValueError(f"Ficha individual no corresponde al Excel: {book.name}")
        answer_count = sum(bool(value) for value in values["03_SEIS_PREGUNTAS"].values())
        if answer_count < 6:
            missing.append(f"{identity['C5']}: faltan {6-answer_count}/6 respuestas individuales")
        if not values["04_MI_DECISION"]["C26"]:
            missing.append(f"{identity['C5']}: falta decisión individual")
    evidence = {}
    for folder, suffixes in (("manuscrito", (".pdf", ".png", ".jpg", ".jpeg")),
                             ("retroalimentacion", (".md", ".txt", ".pdf")),
                             ("evidencia_visor", (".pdf", ".png", ".jpg", ".jpeg"))):
        files = sorted(p for p in (closure / folder).iterdir() if p.is_file() and p.suffix.lower() in suffixes and p.stat().st_size > 20)
        if not files:
            missing.append(f"Falta evidencia real en {folder}/")
        evidence[folder] = [p.name for p in files]
    result = {"grupo": group, "operacion": config["operacion"], "individuales": len(individuals),
              "respuestas_grupales": group_count,
              "decision": "escrita" if all(decision.values()) else "incompleta",
              "archivos_evidencia": evidence, "estado_documental": "COMPLETA" if not missing else "INCOMPLETA",
              "pendientes": missing,
              "revision_humana": "Pendiente: legibilidad, participación y rigor de respuestas manuscritas."}
    if strict and missing:
        raise ValueError("; ".join(missing[:8]))
    return result


def commit(root: Path, confirm: bool, *, allow_incomplete: bool = False) -> dict:
    if not confirm:
        raise PermissionError("Falta --confirmar-representante; no se hizo commit")
    config = _config(root)
    origin, branch = _repo(root, config)
    result = verify(root, strict=not allow_incomplete)
    relative = f"cierre/{SESSION_DATE}"
    if _run(["git", "log", "--format=%H", "--", relative], root):
        raise ValueError("El cierre ya tiene un commit previo; no se crea otro")
    status = _run(["git", "status", "--porcelain", "--untracked-files=all"], root).splitlines()
    if any(not line[3:].strip('"').replace("\\", "/").startswith(relative + "/") for line in status):
        raise ValueError("Hay cambios fuera de la carpeta de cierre")
    closure = root / relative
    summary = closure / "RESUMEN_ENTREGA.json"
    if summary.exists():
        raise FileExistsError("Ya existe un resumen; revisar antes de repetir el commit")
    files = sorted(p for p in closure.rglob("*") if p.is_file())
    result["archivos_sha256"] = {p.relative_to(closure).as_posix(): _sha(p) for p in files}
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run(["git", "add", "--", relative], root)
    _run(["git", "commit", "-m", f"Laboratorio 01 {config['grupo']} {SESSION_DATE} cierre grupal"], root)
    sha = _run(["git", "rev-parse", "HEAD"], root)
    changed = [name for name in _run(["git", "show", "--pretty=format:", "--name-only", "HEAD"], root).splitlines() if name]
    if not changed or any(not name.startswith(relative + "/") for name in changed):
        raise RuntimeError("El commit incluye archivos ajenos al cierre")
    return {"grupo": config["grupo"], "commit_sha": sha, "rama": branch, "origin": origin,
            "estado": "COMMIT_LOCAL_VERIFICADO; NO IMPLICA PUSH",
            "estado_documental": result["estado_documental"], "archivos": len(changed)}


def _local_commit_receipt(root: Path) -> dict:
    """Solo acredita un commit si HEAD contiene el cierre y no se cambió después."""
    relative = f"cierre/{SESSION_DATE}"
    if not (root / ".git").exists():
        return {"estado": "SIN_COMMIT", "nota": "Kit sin repositorio Git inicializado"}
    try:
        sha = _run(["git", "rev-parse", "HEAD"], root)
        changed = [name for name in _run(["git", "show", "--pretty=format:", "--name-only", "HEAD"], root).splitlines() if name]
        dirty = _run(["git", "status", "--porcelain", "--untracked-files=all", "--", relative], root)
        if changed and all(name.startswith(relative + "/") for name in changed) and not dirty:
            return {"estado": "COMMIT_LOCAL_VERIFICADO", "commit_sha": sha,
                    "nota": "No acredita push ni evaluación docente"}
    except RuntimeError:
        pass
    return {"estado": "SIN_COMMIT_VERIFICADO", "nota": "No se acreditó HEAD como cierre limpio"}


def make_zip(root: Path, output: Path) -> Path:
    """Crea SIEMPRE una entrega verificable, aunque no exista Git ni respuestas completas."""
    config = _config(root)
    closure = root / "cierre" / SESSION_DATE
    if not closure.exists():
        prepare(root)
    result = verify(root, strict=False)
    if output.exists():
        raise FileExistsError("El ZIP docente ya existe; no se sobrescribe")
    if output.with_suffix(output.suffix + ".sha256").exists():
        raise FileExistsError("El comprobante SHA-256 ya existe; no se sobrescribe")
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("El ZIP docente debe quedar fuera del repositorio del grupo")
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema": "kai-lab01-entrega/2", "grupo": config["grupo"],
               "operacion": config["operacion"], "fecha": SESSION_DATE,
               "estado_documental": result["estado_documental"],
               "pendientes": result["pendientes"], "control": result["revision_humana"],
               "git": _local_commit_receipt(root), "push": "NO_VERIFICADO"}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        for path in sorted(p for p in closure.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(closure).as_posix())
        archive.writestr("RECIBO_ENTREGA.json", json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        if receipt["git"]["estado"] == "COMMIT_LOCAL_VERIFICADO":
            legacy_receipt = {"grupo": config["grupo"], "commit_sha": receipt["git"]["commit_sha"],
                              "estado": "COMMIT_LOCAL_VERIFICADO", "nota": receipt["git"]["nota"]}
            archive.writestr("RECIBO_COMMIT_LOCAL.json", json.dumps(legacy_receipt, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Error de integridad del ZIP entregable")
    checksum = _sha(output)
    output.with_suffix(output.suffix + ".sha256").write_text(f"{checksum}  {output.name}\n", encoding="ascii")
    return output


def push(root: Path, confirm: bool, authorize: bool) -> dict:
    if not confirm or not authorize:
        raise PermissionError("Se requieren --confirmar-representante y --autorizar-envio; no se hizo push")
    config = _config(root)
    origin, branch = _repo(root, config)
    sha = _run(["git", "rev-parse", "HEAD"], root)
    relative = f"cierre/{SESSION_DATE}"
    changed = [name for name in _run(["git", "show", "--pretty=format:", "--name-only", "HEAD"], root).splitlines() if name]
    if not changed or any(not name.startswith(relative + "/") for name in changed):
        raise ValueError("HEAD no es el commit único de la sesión")
    if _run(["git", "status", "--porcelain"], root):
        raise ValueError("Hay cambios locales sin confirmar")
    _run(["gh", "auth", "status"], root)
    visibility = json.loads(_run(["gh", "repo", "view", origin, "--json", "visibility"], root))
    if visibility.get("visibility") != "PRIVATE":
        raise ValueError("El repositorio grupal no se confirmó privado")
    _run(["git", "push", "origin", branch], root)
    remote = _run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], root).split()
    if not remote or remote[0] != sha:
        raise RuntimeError("El SHA remoto no coincide con el commit local")
    return {"grupo": config["grupo"], "commit_sha": sha, "estado": "PUSH_VERIFICADO", "origin": origin}


def main() -> int:
    p = argparse.ArgumentParser(description="Cierre grupal · Lab 01 v2")
    p.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar")
    sub.add_parser("incorporar")
    export = sub.add_parser("exportar-individual")
    export.add_argument("--alias", required=True)
    export.add_argument("--salida", type=Path, required=True)
    imp = sub.add_parser("importar")
    imp.add_argument("--desde", type=Path, required=True)
    check = sub.add_parser("verificar")
    check.add_argument("--permitir-incompleta", action="store_true")
    co = sub.add_parser("commit")
    co.add_argument("--confirmar-representante", action="store_true")
    co.add_argument("--permitir-incompleta", action="store_true")
    zi = sub.add_parser("zip")
    zi.add_argument("--salida", type=Path, required=True)
    pu = sub.add_parser("push")
    pu.add_argument("--confirmar-representante", action="store_true")
    pu.add_argument("--autorizar-envio", action="store_true")
    args = p.parse_args()
    try:
        root = args.raiz.resolve()
        if args.cmd == "preparar":
            result = {"cierre": str(prepare(root))}
        elif args.cmd == "incorporar":
            result = incorporate(root)
        elif args.cmd == "exportar-individual":
            result = {"zip_individual": str(export_student(root, args.alias, args.salida.resolve()))}
        elif args.cmd == "importar":
            result = import_student(root, args.desde.resolve())
        elif args.cmd == "verificar":
            result = verify(root, strict=not args.permitir_incompleta)
        elif args.cmd == "commit":
            result = commit(root, args.confirmar_representante, allow_incomplete=args.permitir_incompleta)
        elif args.cmd == "zip":
            result = {"zip": str(make_zip(root, args.salida.resolve()))}
        else:
            result = push(root, args.confirmar_representante, args.autorizar_envio)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, PermissionError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"CIERRE LAB01: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
