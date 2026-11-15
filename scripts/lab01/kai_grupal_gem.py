"""Integración grupal privada de evidencias GEM; sin publicación ni calificación.

El tutor registra intervenciones efectivamente recibidas. Este motor comprueba
identidad, integridad y acuerdos explícitos; no interpreta semánticamente el
consenso ni sustituye la evaluación docente.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Iterator
from uuid import UUID, uuid4
import zipfile

from kai_lab01_v2 import GROUP, SESSION_DATE, edit_copy
from gem_integridad import bloqueo
from lab01_common_v2 import _alias, _config, workbook_values


SCHEMA = "gem-grupal/1"
TOPICS = tuple(f"PREGUNTA_{n}" for n in range(1, 7)) + ("S11", "S12", "DECISION_FINAL")
STEPS = tuple(f"P09.{n}" for n in range(1, 7)) + tuple(f"P10.{n}" for n in range(1, 7)) + ("DECISION_FINAL",)
ATTACHMENT_TYPES = ("manuscrito", "retroalimentacion", "evidencia_visor")
DECISION_CELLS = {"diagnostico": "D11", "costos": "D14", "recomendacion": "D26", "condicion": "D29"}
MAX_ATTACHMENT = 35_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: dict | list) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _text(value: str, name: str, *, limit: int = 12000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError(f"{name}: texto real no vacío, de hasta {limit} caracteres")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValueError(f"{name}: contiene caracteres de control")
    return value.strip()


def _uuid(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Identificador de expediente o entrega inválido")
    try:
        result = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Se requiere un UUID íntegro") from exc
    if result != value:
        raise ValueError("El UUID debe estar en su forma canónica")
    return result


def _directory(root: Path, expediente: str) -> Path:
    base = root.resolve() / ".gem_grupal"
    if base.is_symlink():
        raise ValueError("La carpeta privada grupal no puede ser un enlace")
    directory = base / _uuid(expediente)
    if base.parent != root.resolve() or directory.resolve().parent != base:
        raise ValueError("Expediente fuera de la carpeta privada del grupo")
    if directory.is_symlink():
        raise ValueError("No se admiten expedientes enlazados a otra carpeta")
    return directory


def _atomic(path: Path, content: bytes) -> None:
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def _exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def _retain(path: Path, content: bytes) -> None:
    """Reutiliza solo los mismos bytes tras una recepción interrumpida."""
    if path.exists():
        if path.is_symlink() or path.read_bytes() != content:
            raise ValueError("Hay evidencia distinta en la ruta de recepción; no se reemplaza")
        return
    _exclusive(path, content)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("El expediente debe ser un objeto JSON")
    return value


def _recover(directory: Path) -> None:
    pending = directory / "transaccion_pendiente.json"
    if not pending.exists():
        return
    transaction = _read(pending)
    if transaction.get("schema") != "gem-grupal-transaccion/1":
        raise ValueError("Transacción grupal desconocida; conservar para revisión")
    state_path = directory / "estado.json"
    current = state_path.read_bytes()
    after = _json(transaction["despues"])
    if _sha(current) not in (transaction["antes_sha256"], _sha(after)):
        raise ValueError("Cambios externos durante el guardado; no se sobrescribe el expediente")
    revision = transaction["despues"]["revision"]
    history = directory / "revisiones" / f"{revision:06d}.json"
    if history.exists() and history.read_bytes() != after:
        raise ValueError("La revisión grupal existente es distinta; no se reemplaza")
    if not history.exists():
        _exclusive(history, after)
    if current != after:
        _atomic(state_path, after)
    pending.unlink()


@contextmanager
def _locked(root: Path, expediente: str) -> Iterator[tuple[Path, dict]]:
    directory = _directory(root, expediente)
    if not directory.is_dir():
        raise FileNotFoundError("No existe el expediente grupal; créalo con el padrón esperado")
    # El SO libera el bloqueo al terminar el proceso, incluso sin finally.
    # Conservar el archivo estable evita crear dos bloqueos por borrado/recreación.
    with bloqueo(directory):
        _recover(directory)
        state = _read(directory / "estado.json")
        config = _config(root)
        if (state.get("schema") != SCHEMA or state.get("expediente_id") != expediente
                or state.get("grupo") != config["grupo"] or state.get("operacion") != config["operacion"]):
            raise ValueError("Expediente de otro grupo, operación o esquema")
        revision = state.get("revision")
        if not isinstance(revision, int) or revision < 0:
            raise ValueError("Revisión grupal inválida")
        history = directory / "revisiones" / f"{revision:06d}.json"
        if not history.is_file() or history.read_bytes() != (directory / "estado.json").read_bytes():
            raise ValueError("El estado grupal difiere de su revisión guardada; conservar para revisión")
        yield directory, state


def _save(directory: Path, before: dict, after: dict) -> None:
    if _read(directory / "estado.json") != before:
        raise ValueError("El expediente cambió durante la operación")
    after["revision"] = before["revision"] + 1
    after["actualizado_utc"] = _now()
    _exclusive(directory / "transaccion_pendiente.json", _json({
        "schema": "gem-grupal-transaccion/1", "antes_sha256": _sha((directory / "estado.json").read_bytes()),
        "despues": after,
    }))
    _recover(directory)
    if _read(directory / "estado.json") != after:
        raise RuntimeError("No se confirmó la persistencia grupal")


def _source(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("Ruta privada de evidencia inválida")
    candidate = directory / name
    if candidate.is_symlink() or directory.resolve() not in candidate.resolve().parents:
        raise ValueError("La evidencia sale del expediente privado")
    return candidate


def _questions(root: Path) -> tuple[list[str], bytes]:
    data = (root / "PREGUNTAS_LAB01_V2.md").read_bytes()
    lines = re.findall(r"^([1-6])\.\s+(.+)$", data.decode("utf-8-sig"), flags=re.MULTILINE)
    if [n for n, _ in lines] != [str(n) for n in range(1, 7)]:
        raise ValueError("No se pudieron recuperar exactamente las seis preguntas oficiales")
    return [value.strip() for _, value in lines], data


def crear(root: Path, padron: list[str]) -> dict:
    config = _config(root)
    aliases = [_alias(value) for value in padron]
    if not aliases or len(aliases) != len(set(aliases)) or len(aliases) > 30:
        raise ValueError("Declara de 1 a 30 alias distintos como padrón esperado; no se infiere de los ZIP recibidos")
    questions, raw = _questions(root)
    expediente = str(uuid4())
    directory = _directory(root, expediente)
    directory.mkdir(parents=True, exist_ok=False)
    state = {"schema": SCHEMA, "expediente_id": expediente, "grupo": config["grupo"],
             "operacion": config["operacion"], "padron_esperado": aliases, "revision": 0,
             "creado_utc": _now(), "actualizado_utc": _now(),
             "preguntas": questions, "preguntas_sha256": _sha(raw), "integrantes": {},
             "intervenciones": [], "acuerdos": {}, "acuerdos_anteriores": [], "adjuntos": [], "exportaciones": []}
    _exclusive(directory / "estado.json", _json(state))
    _exclusive(directory / "revisiones/000000.json", _json(state))
    _exclusive(directory / "fuentes/PREGUNTAS_LAB01_V2.md", raw)
    return {"expediente_id": expediente, "grupo": config["grupo"], "padron_esperado": aliases,
            "directorio_privado": str(directory), "estado": "EN_INTEGRACION"}


def _verified_package(root: Path, data: bytes) -> dict:
    from entrega_gem import verificar_paquete
    from piloto_supervisado_gem import INDIVIDUAL_SCHEMA
    package = verificar_paquete(root, data)
    receipt = package["recibo"]
    config = _config(root)
    legacy = receipt.get("schema") == "gem-individual/1"
    pilot = receipt.get("schema") == INDIVIDUAL_SCHEMA
    if (not (legacy or pilot) or receipt.get("grupo") != config["grupo"]
            or receipt.get("operacion") != config["operacion"]
            or receipt.get("estado_academico") != ("COMPLETO" if legacy else "PENDIENTE_REVISION_DOCENTE")):
        raise ValueError("Se requiere una entrega individual completa, íntegra y de esta operación")
    _uuid(receipt.get("entrega_id"))
    _alias(receipt.get("alias", ""))
    route = package["recorrido"]
    if (route.get("schema") != "gem-recorrido/1" or route.get("grupo") != config["grupo"]
            or route.get("operacion") != config["operacion"] or route.get("alias") != receipt["alias"]):
        raise ValueError("El recorrido no coincide con la identidad del recibo")
    for step in STEPS:
        activity = route.get("actividades", {}).get(step, {})
        if activity.get("estado") != "comprendido" or not activity.get("intentos"):
            raise ValueError(f"La entrega individual no registra cierre formativo de {step}")
    if not isinstance(package.get("archivos"), dict) or not isinstance(package.get("progreso"), dict):
        raise ValueError("La entrega no contiene sus evidencias y progreso")
    if package["proyeccion"]["dimensiones"]["VERIFICACION_ACADEMICA"] != "PENDIENTE_DOCENTE":
        raise ValueError("No se acepta certificación académica declarada en un paquete")
    return package


def _publication(root: Path, sobre: Path, receipt: Path, entrega: str) -> dict:
    from publicacion_gem import verificar_recibo
    verified = verificar_recibo(root, sobre, receipt)
    if (verified.get("estado") != "PUBLICADO_GITHUB_VERIFICADO"
            or verified.get("sobre_sha256") != _sha(sobre.read_bytes())
            or verified.get("entrega_id") != entrega or verified.get("grupo") != _config(root)["grupo"]
            or not re.fullmatch(r"[0-9a-f]{40}", verified.get("commit", ""))):
        raise ValueError("La publicación verificada no corresponde al sobre y entrega recibidos")
    return verified


def recibir(root: Path, expediente: str, *, paquete: Path | None = None,
            sobre: Path | None = None, clave: Path | None = None,
            recibo_publicacion: Path | None = None) -> dict:
    if paquete is not None:
        if any(item is not None for item in (sobre, clave, recibo_publicacion)):
            raise ValueError("La recepción local usa solo --paquete. Para acreditar GitHub usa sobre, clave y recibo")
        if not paquete.is_file() or paquete.stat().st_size > 100_000_000:
            raise ValueError("Paquete individual inexistente o mayor de 100 MB")
        data = paquete.read_bytes()
    else:
        if sobre is None or clave is None:
            raise ValueError("Declara un ZIP académico local o un sobre con su clave restringida")
        from publicacion_gem import abrir_sobre
        data = abrir_sobre(root, sobre, clave)
    package = _verified_package(root, data)
    receipt = package["recibo"]
    alias, delivery = receipt["alias"], receipt["entrega_id"]
    proof = (_publication(root, sobre, recibo_publicacion, delivery)
             if recibo_publicacion is not None else {"estado": "LOCAL_SIN_PUBLICACION"})
    with _locked(root, expediente) as (directory, state):
        if alias not in state["padron_esperado"]:
            raise ValueError("El alias no pertenece al padrón declarado del equipo")
        old = state["integrantes"].get(alias)
        if old and (old["entrega_id"] != delivery or old["paquete_sha256"] != _sha(data)):
            raise ValueError("El alias ya tiene otra entrega. No se reemplaza; revisen la discrepancia o creen otro expediente")
        if any(entry["entrega_id"] == delivery and name != alias for name, entry in state["integrantes"].items()):
            raise ValueError("Identificador de entrega duplicado entre integrantes")
        if old and (old["publicacion"].get("estado") == "PUBLICADO_GITHUB_VERIFICADO"
                    or proof["estado"] == "LOCAL_SIN_PUBLICACION"):
            return {"alias": alias, "entrega_id": delivery, "estado": "YA_RECIBIDO_SIN_DUPLICAR",
                    "publicacion": old["publicacion"]["estado"]}
        after = deepcopy(state)
        record = old.copy() if old else {"entrega_id": delivery, "paquete_sha256": _sha(data),
            "paquete": f"individuales/{delivery}.zip", "recibido_utc": _now(),
            "recorrido_revision": package["recorrido"].get("revision")}
        if not old:
            _retain(directory / record["paquete"], data)
        record["publicacion"] = proof
        if proof["estado"] == "PUBLICADO_GITHUB_VERIFICADO":
            record["sobre"] = f"procedencia/{delivery}_sobre.zip"
            record["recibo_publicacion"] = f"procedencia/{delivery}_publicacion.json"
            record["recibo_publicacion_sha256"] = _sha(recibo_publicacion.read_bytes())
            _retain(directory / record["sobre"], sobre.read_bytes())
            _retain(directory / record["recibo_publicacion"], recibo_publicacion.read_bytes())
        after["integrantes"][alias] = record
        _save(directory, state, after)
        return {"alias": alias, "entrega_id": delivery, "estado": "RECIBIDO_DOCUMENTALMENTE",
                "verificacion_academica": "PENDIENTE_DOCENTE",
                "publicacion": proof["estado"], "revision": after["revision"]}


def _packages(root: Path, directory: Path, state: dict) -> dict[str, dict]:
    result = {}
    for alias, entry in state["integrantes"].items():
        path = _source(directory, entry["paquete"])
        data = path.read_bytes()
        if _sha(data) != entry["paquete_sha256"]:
            raise ValueError(f"La copia académica recibida de {alias} cambió")
        package = _verified_package(root, data)
        receipt = package["recibo"]
        if receipt["alias"] != alias or receipt["entrega_id"] != entry["entrega_id"]:
            raise ValueError("La identidad del paquete guardado cambió")
        result[alias] = package
    return result


def comparar(root: Path, expediente: str) -> dict:
    with _locked(root, expediente) as (directory, state):
        packages = _packages(root, directory, state)
        results = {}
        for step in STEPS:
            answers = []
            for alias, package in packages.items():
                attempts = package["recorrido"]["actividades"][step]["intentos"]
                attempt = attempts[-1]
                answers.append({"alias": alias, "respuesta": attempt.get("respuesta", ""),
                    "interpretacion": attempt.get("interpretacion", ""), "conclusion": attempt.get("conclusion", ""),
                    "evidencias": attempt.get("evidencias", []), "entrega_id": package["recibo"]["entrega_id"]})
            signatures = {tuple(answer.get(key, "") for key in ("respuesta", "interpretacion", "conclusion")) for answer in answers}
            results[step] = {"diferencia_textual": len(signatures) > 1, "interpretaciones": answers}
        for number in range(1, 7):
            key = f"pregunta_{number}"
            answers = [{"alias": alias,
                        "respuesta": package["progreso"].get("respuestas_breves", {}).get(key, ""),
                        "historial_respuestas": package["progreso"].get("respuestas_por_etapa", {}).get(key, []),
                        "entrega_id": package["recibo"]["entrega_id"]}
                       for alias, package in packages.items()]
            results[f"PREGUNTA_{number}"] = {
                "pregunta_oficial": state["preguntas"][number-1],
                "diferencia_textual": len({answer["respuesta"] for answer in answers}) > 1,
                "interpretaciones": answers,
                "fuente": "Registro breve Lab01; consultar XLSX incluido para texto íntegro si supera 600 caracteres"}
        return {"grupo": state["grupo"], "expediente_id": expediente, "pasos": results,
                "limite": "Comparación textual de respuestas reales; las diferencias conceptuales se discuten, no se infieren automáticamente"}


def intervenir(root: Path, expediente: str, *, alias: str, tema: str, turno_id: str,
               texto: str, tipo: str = "aporte", propuesta_id: str | None = None) -> dict:
    alias = _alias(alias)
    text = _text(texto, "intervención real")
    turn = _text(turno_id, "turno", limit=120)
    if tema not in TOPICS or tipo not in ("aporte", "propuesta", "confirmacion"):
        raise ValueError("Tema o tipo de intervención grupal inválido")
    with _locked(root, expediente) as (directory, state):
        if alias not in state["padron_esperado"] or alias not in state["integrantes"]:
            raise ValueError("Solo intervienen integrantes del padrón con su evidencia individual recibida")
        if any(item["turno_id"] == turn for item in state["intervenciones"]):
            raise ValueError("El turno ya está registrado; no se duplica ni reutiliza")
        if tipo == "confirmacion":
            proposal = next((item for item in state["intervenciones"] if item["id"] == propuesta_id), None)
            if not proposal or proposal["tipo"] != "propuesta" or proposal["tema"] != tema:
                raise ValueError("La confirmación debe identificar una propuesta real del mismo tema")
        elif propuesta_id is not None:
            raise ValueError("Solo una confirmación puede referirse a una propuesta")
        after = deepcopy(state)
        record = {"id": str(uuid4()), "alias": alias, "tema": tema, "turno_id": turn,
                  "texto": text, "tipo": tipo, "propuesta_id": propuesta_id, "fecha_utc": _now(),
                  "origen": "intervencion_declarada_real_por_el_tutor; autoría no autenticada por el script"}
        after["intervenciones"].append(record)
        if tema in after["acuerdos"]:
            previous = after["acuerdos"].pop(tema)
            previous["motivo_reapertura"] = "Nueva intervención sobre el tema; confirmar el acuerdo vigente"
            after["acuerdos_anteriores"].append(previous)
        _save(directory, state, after)
        return {"intervencion_id": record["id"], "tema": tema, "revision": after["revision"]}


def acordar(root: Path, expediente: str, *, tema: str, propuesta_id: str,
            confirmaciones: list[str], extractos: dict[str, str] | None = None) -> dict:
    if tema not in TOPICS:
        raise ValueError("Tema grupal inválido")
    with _locked(root, expediente) as (directory, state):
        items = {item["id"]: item for item in state["intervenciones"]}
        proposal = items.get(propuesta_id)
        if not proposal or proposal["tema"] != tema or proposal["tipo"] != "propuesta":
            raise ValueError("El acuerdo debe usar literalmente una propuesta registrada del equipo")
        if len(confirmaciones) != len(set(confirmaciones)):
            raise ValueError("Hay confirmaciones duplicadas")
        accepted = []
        proposal_index = state["intervenciones"].index(proposal)
        for identifier in confirmaciones:
            item = items.get(identifier)
            if (not item or item["tipo"] != "confirmacion" or item["tema"] != tema
                    or item["propuesta_id"] != propuesta_id
                    or state["intervenciones"].index(item) <= proposal_index):
                raise ValueError("Cada integrante debe confirmar explícitamente esta propuesta después de conocerla")
            accepted.append(item["alias"])
        if len(accepted) != len(set(accepted)) or set(accepted) != set(state["padron_esperado"]):
            raise ValueError("Falta la confirmación explícita de cada integrante del padrón; no se presume consenso")
        if set(state["integrantes"]) != set(state["padron_esperado"]):
            raise ValueError("Faltan evidencias individuales del padrón esperado")
        # Una objeción o propuesta posterior deja obsoleta la ronda anterior.
        last_discussion = max((n for n, item in enumerate(state["intervenciones"])
                               if item["tema"] == tema and item["tipo"] != "confirmacion"), default=-1)
        if any(state["intervenciones"].index(items[i]) <= last_discussion for i in confirmaciones):
            raise ValueError("Hubo deliberación posterior; confirmen de nuevo el texto acordado")
        selected = extractos or {}
        if tema == "DECISION_FINAL":
            if set(selected) != set(DECISION_CELLS):
                raise ValueError("La decisión necesita extractos reales de diagnóstico, costos, recomendación y condición")
            selected = {key: _text(value, key) for key, value in selected.items()}
            if any(value not in proposal["texto"] for value in selected.values()):
                raise ValueError("Los extractos de decisión deben aparecer literalmente en la propuesta real")
        elif selected:
            raise ValueError("Los extractos estructurados se reservan para la decisión final")
        agreement = {"tema": tema, "texto": proposal["texto"], "propuesta_id": propuesta_id,
                     "confirmaciones": confirmaciones, "participantes": accepted,
                     "extractos": selected, "fecha_utc": _now(),
                     "limite": "Acuerdo declarado por participantes; sin aprobación académica automática"}
        after = deepcopy(state)
        if tema in after["acuerdos"]:
            after["acuerdos_anteriores"].append(after["acuerdos"][tema])
        after["acuerdos"][tema] = agreement
        _save(directory, state, after)
        return {"tema": tema, "estado": "ACUERDO_REGISTRADO", "participantes": accepted,
                "revision": after["revision"]}


def adjuntar(root: Path, expediente: str, *, tipo: str, archivo: Path, descripcion: str) -> dict:
    if tipo not in ATTACHMENT_TYPES:
        raise ValueError("Tipo de adjunto inválido")
    description = _text(descripcion, "descripción de evidencia", limit=1500)
    permitted = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    if tipo == "retroalimentacion":
        permitted += (".md", ".txt", ".docx")
    suffix = archivo.suffix.lower()
    if not archivo.is_file() or archivo.is_symlink() or suffix not in permitted:
        raise ValueError("Adjunta un documento o imagen regular, sin enlaces ni ejecutables")
    if not 0 < archivo.stat().st_size <= MAX_ATTACHMENT:
        raise ValueError("El adjunto está vacío o supera 35 MB")
    data = archivo.read_bytes()
    # El sufijo no permite convertir un texto renombrado en foto/manuscrito.
    signatures = {".pdf": data.startswith(b"%PDF-"), ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
                  ".jpg": data.startswith(b"\xff\xd8\xff"), ".jpeg": data.startswith(b"\xff\xd8\xff"),
                  ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP"}
    if suffix in signatures and not signatures[suffix]:
        raise ValueError("El contenido del adjunto no corresponde al tipo de imagen o PDF declarado")
    if suffix in (".txt", ".md"):
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("La retroalimentación de texto debe poder leerse en UTF-8") from exc
    if suffix == ".docx":
        from gem_integridad import leer_zip
        # Aplica los límites de tamaño, relación de compresión y rutas antes
        # de descomprimir el DOCX recibido, igual que las entregas individuales.
        document = leer_zip(data)
        if "word/document.xml" not in document or "[Content_Types].xml" not in document:
            raise ValueError("El DOCX de retroalimentación está incompleto")
    with _locked(root, expediente) as (directory, state):
        if any(item["tipo"] == tipo and item["sha256"] == _sha(data) for item in state["adjuntos"]):
            raise ValueError("Este adjunto ya está registrado en la categoría")
        identifier = str(uuid4())
        name = f"adjuntos/{tipo}/{identifier}{archivo.suffix.lower()}"
        _exclusive(directory / name, data)
        after = deepcopy(state)
        after["adjuntos"].append({"id": identifier, "tipo": tipo, "archivo": name,
            "sha256": _sha(data), "descripcion": description, "fecha_utc": _now(),
            "revision_visual": "Pendiente de cotejo humano; el motor solo comprueba bytes y presencia"})
        _save(directory, state, after)
        return {"adjunto_id": identifier, "tipo": tipo, "sha256": _sha(data), "revision": after["revision"]}


def _report(root: Path, directory: Path, state: dict, *, verificar_red: bool) -> dict:
    packages = _packages(root, directory, state)
    missing = [f"Falta ZIP individual de {alias}" for alias in state["padron_esperado"] if alias not in packages]
    publications = {}
    for alias, entry in state["integrantes"].items():
        proof = entry["publicacion"]
        if proof.get("estado") == "PUBLICADO_GITHUB_VERIFICADO":
            envelope = _source(directory, entry["sobre"])
            receipt = _source(directory, entry["recibo_publicacion"])
            if (_sha(envelope.read_bytes()) != proof["sobre_sha256"]
                    or _sha(receipt.read_bytes()) != entry["recibo_publicacion_sha256"]):
                raise ValueError("La procedencia guardada cambió; no se acredita publicación")
            if verificar_red:
                try:
                    proof = _publication(root, envelope, receipt, entry["entrega_id"])
                except (ValueError, OSError, RuntimeError) as exc:
                    proof = {"estado": "PUBLICACION_NO_REVERIFICADA", "detalle": str(exc)}
        publications[alias] = proof
        if proof.get("estado") != "PUBLICADO_GITHUB_VERIFICADO":
            missing.append(f"{alias}: falta confirmar el depósito en el GitHub original del grupo")
    missing += [f"Falta acuerdo explícito: {topic}" for topic in TOPICS if topic not in state["acuerdos"]]
    for kind in ATTACHMENT_TYPES:
        attachments = [item for item in state["adjuntos"] if item["tipo"] == kind]
        if not attachments:
            missing.append(f"Falta adjunto: {kind}")
        for item in attachments:
            if _sha(_source(directory, item["archivo"]).read_bytes()) != item["sha256"]:
                raise ValueError("La evidencia adjunta fue modificada después de recibirse")
    if _sha(_source(directory, "fuentes/PREGUNTAS_LAB01_V2.md").read_bytes()) != state["preguntas_sha256"]:
        raise ValueError("Cambió la copia de las seis preguntas oficiales")
    academic = {alias: package["proyeccion"]["dimensiones"]["VERIFICACION_ACADEMICA"]
                for alias, package in packages.items()}
    return {"schema": "gem-grupal-estado/1", "expediente_id": state["expediente_id"],
            "grupo": state["grupo"], "operacion": state["operacion"], "revision": state["revision"],
            "estado_documental": "INCOMPLETO" if missing else "COMPLETO", "pendientes": missing,
            "integrantes_recibidos": list(packages), "padron_esperado": state["padron_esperado"],
            "acuerdos": list(state["acuerdos"]), "publicaciones": publications,
            "verificacion_individual": academic,
            "dimensiones": {"INTEGRIDAD_DOCUMENTAL": "INTEGRA" if not missing else "INCOMPLETA",
                           "COMPLETITUD_FORMATIVA": "COMPLETA" if len(packages)==len(state["padron_esperado"]) else "EN_CURSO",
                           "VERIFICACION_ACADEMICA": "PENDIENTE_DOCENTE",
                           "PUBLICACION_REMOTA": "VERIFICADA" if verificar_red and publications and all(
                               p.get("estado")=="PUBLICADO_GITHUB_VERIFICADO" for p in publications.values())
                               else "NO_VERIFICADA",
                           "CALIFICACION_DOCENTE": "NO_EMITIDA"},
            "red_reverificada_en_esta_consulta": verificar_red, "evaluacion_docente": "PENDIENTE",
            "limite": "Completitud e integridad documentales; no certifica autoría, comprensión, consenso semántico ni nota"}


def estado(root: Path, expediente: str, *, verificar_red: bool = False) -> dict:
    with _locked(root, expediente) as (directory, state):
        return _report(root, directory, state, verificar_red=verificar_red)


def _workbooks(root: Path, directory: Path, state: dict, target: Path) -> tuple[Path, Path]:
    config = _config(root)
    packages = _packages(root, directory, state)
    master = root / "plantilla" / GROUP
    master_hash = _sha(master.read_bytes())
    if master_hash != config["grupal_sha256"]:
        raise ValueError("La plantilla grupal no coincide con el maestro protegido")
    target.mkdir(parents=True, exist_ok=False)
    book = target / f"GEM_{state['grupo']}_GRUPAL.xlsx"
    shutil.copyfile(master, book)
    edits = {"00_EQUIPO": {"D5": state["grupo"], "D6": state["operacion"], "D7": SESSION_DATE,
                           "D8": config.get("repo_url", "")}}
    for position in range(9):
        row = position + 15
        if position < len(state["padron_esperado"]):
            alias = state["padron_esperado"][position]
            package = packages.get(alias)
            edits["00_EQUIPO"].update({f"B{row}": alias,
                f"C{row}": package["progreso"].get("excel", "Ver ZIP académico") if package else "",
                f"D{row}": "SÍ" if package else "PENDIENTE"})
        else:
            edits["00_EQUIPO"].update({f"B{row}": "", f"C{row}": "", f"D{row}": ""})
    for n in range(1, 7):
        agreement = state["acuerdos"].get(f"PREGUNTA_{n}")
        if agreement:
            edits.setdefault("02_6_RESPUESTAS", {})[f"D{n+6}"] = agreement["texto"]
    decision = state["acuerdos"].get("DECISION_FINAL")
    if decision:
        edits["03_DECISION_FINAL"] = {cell: decision["extractos"][key] for key, cell in DECISION_CELLS.items()}
    edit_copy(book, edits)
    if workbook_values(book, {sheet: list(cells) for sheet, cells in edits.items()}) != edits:
        raise RuntimeError("La lectura del Excel grupal no coincide con los acuerdos")
    if _sha(master.read_bytes()) != master_hash:
        raise RuntimeError("La plantilla maestra cambió")
    # Este libro nuevo evita alterar la estructura de la plantilla histórica.
    from openpyxl import Workbook
    integration = Workbook()
    sheet = integration.active
    sheet.title = "S11_S12"
    rows = [["Grupo", state["grupo"]], ["Operación", state["operacion"]],
            ["Expediente", state["expediente_id"]], ["Revisión", str(state["revision"])],
            ["Límite", "Síntesis consensuadas declaradas, sin calificación docente"],
            ["Tema", "Texto real acordado", "Participantes", "Propuesta"]]
    rows += [[topic, state["acuerdos"].get(topic, {}).get("texto", "PENDIENTE"),
              ", ".join(state["acuerdos"].get(topic, {}).get("participantes", [])),
              state["acuerdos"].get(topic, {}).get("propuesta_id", "")]
             for topic in ("S11", "S12", "DECISION_FINAL")]
    for row in rows:
        sheet.append(row)
        for cell in sheet[sheet.max_row]:
            if cell.value is not None:
                cell.data_type = "s"
    sheet.column_dimensions["A"].width = 23
    sheet.column_dimensions["B"].width = 100
    sheet.column_dimensions["C"].width = 32
    sheet.column_dimensions["D"].width = 42
    from openpyxl.styles import Alignment, Font, PatternFill
    for row in sheet:
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in sheet[6]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17394D")
    matrix = integration.create_sheet("Interpretaciones")
    matrix.append(["Alias", "Paso", "Respuesta real", "Interpretación", "Conclusión", "Entrega"])
    for alias, package in packages.items():
        for step in STEPS:
            attempt = package["recorrido"]["actividades"][step]["intentos"][-1]
            matrix.append([alias, step, attempt.get("respuesta", ""), attempt.get("interpretacion", ""),
                           attempt.get("conclusion", ""), package["recibo"]["entrega_id"]])
    for row in matrix:
        for cell in row:
            if cell.value is not None:
                cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for column in "CDE":
        matrix.column_dimensions[column].width = 65
    matrix.column_dimensions["A"].width = 25
    matrix.column_dimensions["B"].width = 20
    matrix.column_dimensions["F"].width = 40
    matrix.freeze_panes = "C2"
    roster = integration.create_sheet("PADRON")
    roster.append(["Alias esperado", "Entrega UUID", "XLSX individual dentro del ZIP", "Recepción",
                   "Publicación", "SHA256 paquete académico", "Verificación académica"])
    for alias in state["padron_esperado"]:
        entry = state["integrantes"].get(alias, {})
        roster.append([alias, entry.get("entrega_id", ""),
            packages.get(alias, {}).get("progreso", {}).get("excel", ""),
            "RECIBIDO" if alias in packages else "PENDIENTE",
            entry.get("publicacion", {}).get("estado", "PENDIENTE"), entry.get("paquete_sha256", ""),
            packages[alias]["proyeccion"]["dimensiones"]["VERIFICACION_ACADEMICA"]
            if alias in packages else "PENDIENTE_DOCENTE"])
    for row in roster:
        for cell in row:
            if cell.value is not None:
                cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for column in "ABCDEFG":
        roster.column_dimensions[column].width = 42
    roster.freeze_panes = "A2"
    extra = target / "INTEGRACION_S11_S12.xlsx"
    integration.save(extra)
    return book, extra


def preparar(root: Path, expediente: str) -> dict:
    with _locked(root, expediente) as (directory, state):
        _packages(root, directory, state)
        target = directory / "excel" / str(uuid4())
        book, extra = _workbooks(root, directory, state, target)
        return {"grupo": state["grupo"], "revision_fuente": state["revision"],
                "excel_grupal": str(book), "excel_s11_s12": str(extra),
                "sha256": {book.name: _sha(book.read_bytes()), extra.name: _sha(extra.read_bytes())},
                "nota": "Copias nuevas, sin reemplazar maestros ni libros anteriores; pendientes conservados"}


def _human(state: dict, report: dict) -> bytes:
    lines = [f"# Integración grupal — {state['grupo']} · {state['operacion']}", "",
             f"Expediente: {state['expediente_id']}", f"Estado documental: {report['estado_documental']}",
             "Verificación académica: PENDIENTE_DOCENTE; calificación: NO_EMITIDA.",
             "Entrega restringida al equipo y docente. Sin nota ni aprobación automática.", "",
             "## Pendientes", ""]
    lines.extend([f"- {item}" for item in report["pendientes"]] or ["Sin pendientes documentales detectados."])
    lines.extend(["", "## Acuerdos reales registrados", ""])
    for topic in TOPICS:
        title = state["preguntas"][int(topic.rsplit("_", 1)[1])-1] if topic.startswith("PREGUNTA_") else topic
        lines += [f"### {topic} — {title}", ""]
        agreement = state["acuerdos"].get(topic)
        if agreement:
            lines += [agreement["texto"], "", "Participantes: " + ", ".join(agreement["participantes"]),
                      "Propuesta: " + agreement["propuesta_id"], ""]
        else:
            lines += ["PENDIENTE; no se ha construido una respuesta por el equipo.", ""]
    lines += ["## Deliberación registrada", ""]
    for item in state["intervenciones"]:
        lines += [f"### {item['tema']} · {item['alias']} · {item['tipo']} · {item['id']}", "",
                  item["texto"], "", f"Turno real declarado: {item['turno_id']}", ""]
    lines += ["## Adjuntos y cotejo", ""]
    for item in state["adjuntos"]:
        lines += [f"- {item['tipo']}: {item['descripcion']} · SHA-256 {item['sha256']}"]
    lines += ["", "La legibilidad, autoría, suficiencia conceptual y calificación deben revisarse por personas.", ""]
    return "\n".join(lines).encode("utf-8")


def exportar_docente(root: Path, expediente: str, salida: Path | None = None) -> dict:
    with _locked(root, expediente) as (directory, state):
        # Revalidación remota fresca. Una indisponibilidad no se convierte en publicación exitosa.
        report = _report(root, directory, state, verificar_red=True)
        target = directory / "excel" / str(uuid4())
        book, extra = _workbooks(root, directory, state, target)
        output = salida or directory / "entregas" / f"GEM_{state['grupo']}_{uuid4().hex}_DOCENTE.zip"
        output = output.resolve()
        if output.suffix.lower() != ".zip":
            raise ValueError("La entrega docente debe tener extensión .zip")
        if root.resolve() in output.parents and directory.resolve() not in output.parents:
            raise ValueError("El ZIP docente con respuestas privadas debe permanecer en el expediente o fuera del repositorio")
        if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
            raise FileExistsError("Ya existe el ZIP docente o su recibo SHA-256; no se sobrescribe")
        files = {"ESTADO_GRUPAL.json": _json(state), "ESTADO_DOCUMENTAL.json": _json(report),
                 "INFORME_GRUPAL.md": _human(state, report), book.name: book.read_bytes(),
                 extra.name: extra.read_bytes(), "fuentes/PREGUNTAS_LAB01_V2.md":
                 _source(directory, "fuentes/PREGUNTAS_LAB01_V2.md").read_bytes()}
        for entry in state["integrantes"].values():
            for key in ("paquete", "sobre", "recibo_publicacion"):
                if key in entry:
                    files[entry[key]] = _source(directory, entry[key]).read_bytes()
        for item in state["adjuntos"]:
            files[item["archivo"]] = _source(directory, item["archivo"]).read_bytes()
        from piloto_supervisado_gem import GROUP_SCHEMA, MODO
        receipt = {"schema": GROUP_SCHEMA, "grupo": state["grupo"], "operacion": state["operacion"],
                   "expediente_id": expediente, "revision": state["revision"], "creado_utc": _now(),
                   "estado_documental": report["estado_documental"], "pendientes": report["pendientes"],
                   "sha256": {name: _sha(data) for name, data in files.items()},
                   "modo": MODO, "dimensiones": report["dimensiones"],
                   "evaluacion_docente": "PENDIENTE", "destino": "DOCENTE_RESTRINGIDO",
                   "nota": "La integridad no autentica la autoría ni aprueba respuestas; no se incluyen claves"}
        files["RECIBO_GRUPAL.json"] = _json(receipt)
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(files):
                raise RuntimeError("El ZIP docente no pasó la lectura de integridad")
            if any(archive.read(name) != content for name, content in files.items()):
                raise RuntimeError("La relectura del ZIP docente difiere de sus evidencias")
        digest = _sha(output.read_bytes())
        _exclusive(output.with_suffix(output.suffix + ".sha256"), (digest + "  " + output.name + "\n").encode("utf-8"))
        after = deepcopy(state)
        after["exportaciones"].append({"archivo": output.name, "sha256": digest,
            "revision_fuente": state["revision"], "estado_documental": report["estado_documental"], "fecha_utc": _now()})
        _save(directory, state, after)
        return {"zip_docente": str(output), "sha256": digest, "estado_documental": report["estado_documental"],
                "pendientes": report["pendientes"], "evaluacion_docente": "PENDIENTE"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Kai Integración GEM · agente grupal, entrega docente restringida")
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("crear")
    new.add_argument("--padron", nargs="+", required=True)
    for name in ("recibir", "estado", "comparar", "intervenir", "acordar", "adjuntar", "preparar", "exportar-docente"):
        command = sub.add_parser(name)
        command.add_argument("--expediente", required=True)
        if name == "recibir":
            command.add_argument("--paquete", type=Path)
            command.add_argument("--sobre", type=Path)
            command.add_argument("--clave", type=Path)
            command.add_argument("--recibo-publicacion", type=Path)
        elif name == "estado":
            command.add_argument("--verificar-red", action="store_true")
        elif name == "intervenir":
            command.add_argument("--alias", required=True)
            command.add_argument("--tema", choices=TOPICS, required=True)
            command.add_argument("--turno-id", required=True)
            command.add_argument("--texto", required=True)
            command.add_argument("--tipo", choices=("aporte", "propuesta", "confirmacion"), default="aporte")
            command.add_argument("--propuesta-id")
        elif name == "acordar":
            command.add_argument("--tema", choices=TOPICS, required=True)
            command.add_argument("--propuesta-id", required=True)
            command.add_argument("--confirmaciones", nargs="+", required=True)
            command.add_argument("--extractos", type=Path, help="JSON de extractos literales para decisión final")
        elif name == "adjuntar":
            command.add_argument("--tipo", choices=ATTACHMENT_TYPES, required=True)
            command.add_argument("--archivo", type=Path, required=True)
            command.add_argument("--descripcion", required=True)
        elif name == "exportar-docente":
            command.add_argument("--salida", type=Path)
    args = parser.parse_args()
    try:
        root = args.raiz.resolve()
        if args.cmd == "crear":
            result = crear(root, args.padron)
        elif args.cmd == "recibir":
            result = recibir(root, args.expediente, paquete=args.paquete, sobre=args.sobre, clave=args.clave,
                             recibo_publicacion=args.recibo_publicacion)
        elif args.cmd == "estado":
            result = estado(root, args.expediente, verificar_red=args.verificar_red)
        elif args.cmd == "comparar":
            result = comparar(root, args.expediente)
        elif args.cmd == "intervenir":
            result = intervenir(root, args.expediente, alias=args.alias, tema=args.tema, turno_id=args.turno_id,
                                texto=args.texto, tipo=args.tipo, propuesta_id=args.propuesta_id)
        elif args.cmd == "acordar":
            result = acordar(root, args.expediente, tema=args.tema, propuesta_id=args.propuesta_id,
                             confirmaciones=args.confirmaciones, extractos=_read(args.extractos) if args.extractos else None)
        elif args.cmd == "adjuntar":
            result = adjuntar(root, args.expediente, tipo=args.tipo, archivo=args.archivo, descripcion=args.descripcion)
        elif args.cmd == "preparar":
            result = preparar(root, args.expediente)
        else:
            result = exportar_docente(root, args.expediente, args.salida)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, RuntimeError, ImportError, zipfile.BadZipFile) as exc:
        print(f"GEM GRUPAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
