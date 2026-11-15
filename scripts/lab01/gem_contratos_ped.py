"""Contratos académicos PED-002, aislados del flujo estudiantil v1.

No evalúa comprensión ni habilita avance. Los hashes acreditan bytes y
consistencia, no autoría, observación de visor o aprobación docente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import uuid
from typing import Any

COMPONENT_VERSION = "gem-ped-002/1.0.0"
MANIFEST_SCHEMA = "gem-source-manifest/2"
EVENT_SCHEMA = "gem-academic-event/2"
RECORRIDO_SCHEMA = "gem-recorrido/2"
FUTURE_SCHEMAS = {
    "gem-deterministic-result/2": "PED_003_NOT_AVAILABLE",
    "gem-visor-snapshot/2": "PED_003_NOT_AVAILABLE",
    "gem-academic-evaluation/2": "PED_004_NOT_AVAILABLE",
}
ACTIVITIES = tuple(f"P09.{i}" for i in range(1, 7)) + tuple(
    f"P10.{i}" for i in range(1, 7)
) + ("DECISION_FINAL",)
LEGACY_STATES = frozenset(("pendiente", "en_curso", "requiere_refuerzo", "comprendido"))
VERIFICATION_STATES = frozenset((
    "SIN_EVALUAR", "EN_REVISION", "REFUERZO", "DOCENTE_PENDIENTE",
    "VERIFICADA", "INVALIDADA", "DECLARADA_HEREDADA",
))
SOURCE_ROLES = frozenset((
    "VIEWER_HTML", "CASE_DATA", "HISTORICAL_RESULTS", "S04_SOURCE",
    "T2_EXCEL", "R11_ZIP", "RUBRIC", "CM03",
))
EXPECTED_SOURCES_G03 = {
    "VIEWER_HTML": ("COPY_G03", "visor/G03_S11_S12_VISOR_INTERACTIVO.html"),
    "CASE_DATA": ("EMBEDDED_CASE_DATA", "visor/G03_S11_S12_VISOR_INTERACTIVO.html#case_data"),
    "HISTORICAL_RESULTS": ("COPY_G03", "datos/G03_RESULTADOS_HISTORICOS.json"),
    "S04_SOURCE": ("COPY_G03", "visor/G03_S04_BASE_FUENTE.json"),
    "T2_EXCEL": ("MASTER_GEM", "T2 Alumnos/h69/G03/Pauta Corregida T2.xlsx"),
    "R11_ZIP": ("MASTER_GEM", "GEM_KAI_R11_CONCILIACION_ECONOMICA_CANDIDATO.zip"),
    "RUBRIC": ("COPY_G03", "docs/ACTIVIDADES_GEM.json"),
    "CM03": ("COPY_G03", "docs/CM03_HECHO_HISTORICO.md"),
}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
REV_RE = re.compile(r"r[0-9]{6}\Z")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}\Z")


class ContractError(ValueError):
    """Error estable para pruebas y consumidores PED-003+; sin texto de alumno."""
    def __init__(self, code: str, path: str = "", detail: str = "") -> None:
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code} @ {path}: {detail}" if path else f"{code}: {detail}")


def canonical_bytes(value: Any) -> bytes:
    """JSON UTF-8, NFC *no* aplicado, claves ordenadas, sin espacios, LF final.

    No normalizar Unicode ni texto literal permite detectar cambios de bytes
    significativos en respuestas. Los hashes de archivo siempre son RAW.
    """
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("SERIALIZATION_INVALID", detail=str(exc)) from exc


def hash_bytes(raw: bytes) -> str:
    if not isinstance(raw, bytes): raise ContractError("TYPE_INVALID", "raw", "bytes")
    return sha256(raw).hexdigest()


def hash_file(path: Path) -> str:
    h = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hash_canonical(value: Any) -> str:
    return hash_bytes(canonical_bytes(value))


def response_hash(student_turns: list[dict]) -> str:
    # Solo turn_id y texto literal, en su orden. No incluye juicio de Kai.
    return hash_canonical([{"turn_id": x["turn_id"], "text": x["text"]}
                           for x in student_turns])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _object(value: Any, path: str) -> dict:
    if not isinstance(value, dict): raise ContractError("TYPE_INVALID", path, "objeto requerido")
    return value


def _keys(value: dict, required: set[str], optional: set[str], path: str) -> None:
    missing, extra = required - set(value), set(value) - required - optional
    if missing: raise ContractError("FIELD_MISSING", path, ",".join(sorted(missing)))
    if extra: raise ContractError("FIELD_UNKNOWN", path, ",".join(sorted(extra)))


def _text(value: Any, path: str, *, max_len: int = 12000, nullable: bool = False) -> None:
    if nullable and value is None: return
    if not isinstance(value, str) or not value.strip() or len(value) > max_len or "\x00" in value:
        raise ContractError("TYPE_INVALID", path, "texto literal no vacío requerido")


def _sha(value: Any, path: str, *, nullable: bool = False) -> None:
    if nullable and value is None: return
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ContractError("HASH_INVALID", path, "SHA-256 hexadecimal minúsculo")


def _revision(value: Any, path: str, *, nullable: bool = False) -> None:
    if nullable and value is None: return
    if not isinstance(value, str) or not REV_RE.fullmatch(value) or value == "r000000":
        raise ContractError("REVISION_INVALID", path, "formato r000001…")


def _id(value: Any, path: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ContractError("IDENTIFIER_INVALID", path, "identificador simple")


def _uuid(value: Any, path: str) -> None:
    try: parsed = uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractError("IDENTIFIER_INVALID", path, "UUIDv4 requerido") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ContractError("IDENTIFIER_INVALID", path, "UUIDv4 canónico requerido")


def _utc(value: Any, path: str) -> None:
    if not isinstance(value, str): raise ContractError("TYPE_INVALID", path, "ISO-8601 UTC")
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise ContractError("TYPE_INVALID", path, "ISO-8601 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ContractError("TYPE_INVALID", path, "zona UTC obligatoria")


def _relative(value: Any, path: str) -> None:
    if not isinstance(value, str) or "\\" in value or ":" in value or "#" in value:
        raise ContractError("PATH_INVALID", path, "ruta POSIX relativa")
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or any(x in (".", "..") for x in p.parts):
        raise ContractError("PATH_INVALID", path, "ruta POSIX relativa")


def _schema(obj: dict, expected: str) -> None:
    if obj.get("schema") != expected:
        raise ContractError("SCHEMA_INCOMPATIBLE", "schema", f"se esperaba {expected}")
    if obj.get("component_version") != COMPONENT_VERSION:
        raise ContractError("VERSION_INCOMPATIBLE", "component_version", COMPONENT_VERSION)


def validate_manifest(value: Any) -> dict:
    m = _object(value, "manifest")
    _keys(m, {"schema", "component_version", "group_id", "model_version", "approval_state",
              "approved_by_ref", "sources", "rubric", "provenance"}, set(), "manifest")
    _schema(m, MANIFEST_SCHEMA)
    if m["group_id"] != "G03": raise ContractError("GROUP_MISMATCH", "group_id", "PED-002 sólo G03")
    _text(m["model_version"], "model_version", max_len=120)
    if m["approval_state"] not in ("PENDIENTE_DOCENTE", "APROBADA_DECLARADA"):
        raise ContractError("STATE_INVALID", "approval_state", "estado de autorización")
    if m["approval_state"] == "PENDIENTE_DOCENTE" and m["approved_by_ref"] is not None:
        raise ContractError("APPROVAL_CONFLICT", "approved_by_ref", "fuente pendiente")
    if m["approval_state"] == "APROBADA_DECLARADA":
        _text(m["approved_by_ref"], "approved_by_ref", max_len=150)
    if not isinstance(m["sources"], list): raise ContractError("TYPE_INVALID", "sources", "lista")
    roles=set()
    for i, raw in enumerate(m["sources"]):
        p=f"sources[{i}]"; s=_object(raw,p)
        _keys(s,{"role","scope","path","sha256","availability"},set(),p)
        role=s["role"]
        if role not in SOURCE_ROLES or role in roles: raise ContractError("SOURCE_ROLE_INVALID",p,str(role))
        roles.add(role)
        if s["scope"] not in ("COPY_G03", "MASTER_GEM", "EMBEDDED_CASE_DATA"):
            raise ContractError("SOURCE_SCOPE_INVALID",p,str(s["scope"]))
        if role == "CASE_DATA":
            if s["scope"] != "EMBEDDED_CASE_DATA" or s["path"] != "visor/G03_S11_S12_VISOR_INTERACTIVO.html#case_data":
                raise ContractError("SOURCE_SCOPE_INVALID",p,"case_data del visor G03")
        else:
            if s["scope"] == "EMBEDDED_CASE_DATA": raise ContractError("SOURCE_SCOPE_INVALID",p)
            _relative(s["path"],p+".path")
        if (s["scope"],s["path"])!=EXPECTED_SOURCES_G03[role]:
            raise ContractError("SOURCE_MISMATCH",p,"ruta/alcance no autorizados para G03")
        if s["availability"] not in ("PRESENT", "MISSING"):
            raise ContractError("STATE_INVALID",p+".availability")
        _sha(s["sha256"],p+".sha256",nullable=s["availability"]=="MISSING")
        if (s["availability"]=="PRESENT") != (s["sha256"] is not None):
            raise ContractError("SOURCE_MISMATCH",p,"disponibilidad/hash")
    if roles != SOURCE_ROLES: raise ContractError("FIELD_MISSING", "sources", ",".join(sorted(SOURCE_ROLES-roles)))
    rub=_object(m["rubric"],"rubric")
    _keys(rub,{"version","path","sha256"},set(),"rubric")
    _text(rub["version"],"rubric.version",max_len=150)
    if rub["path"] != "docs/ACTIVIDADES_GEM.json": raise ContractError("RUBRIC_MISSING","rubric.path")
    _sha(rub["sha256"],"rubric.sha256")
    rs=next(x for x in m["sources"] if x["role"]=="RUBRIC")
    if rs["sha256"] != rub["sha256"] or rs["path"] != rub["path"]:
        raise ContractError("RUBRIC_MISMATCH","rubric")
    prov=_object(m["provenance"],"provenance")
    _keys(prov,{"generated_at_utc","origin","authorization_evidence_ref"},set(),"provenance")
    _utc(prov["generated_at_utc"],"provenance.generated_at_utc")
    _text(prov["origin"],"provenance.origin",max_len=250)
    if prov["authorization_evidence_ref"] is not None:
        _text(prov["authorization_evidence_ref"],"provenance.authorization_evidence_ref",max_len=150)
    return m


def manifest_hash(manifest: dict) -> str:
    validate_manifest(manifest)
    return hash_canonical(manifest)  # sin campo autocontenido de hash


def approval_effective(manifest: dict) -> bool:
    validate_manifest(manifest)
    # PED-002 carece de autenticación docente; una declaración no es prueba.
    return False


def validate_manifest_files(manifest: dict, copy_root: Path, master_root: Path) -> dict[str,str]:
    """Comprueba bytes RAW de archivos confiados por ruta fija del manifiesto.

    No transforma el atributo de aprobación en autorización efectiva.
    """
    validate_manifest(manifest)
    roots={"COPY_G03":Path(copy_root).resolve(),"MASTER_GEM":Path(master_root).resolve()}
    observed={}
    for s in manifest["sources"]:
        if s["role"]=="CASE_DATA":
            viewer=roots["COPY_G03"]/"visor/G03_S11_S12_VISOR_INTERACTIVO.html"
            match=re.search(rb'<script[^>]*id="case_data"[^>]*>(.*?)</script>',viewer.read_bytes(),re.S)
            if not match: raise ContractError("SOURCE_MISSING",s["role"],"case_data")
            actual=hash_bytes(match.group(1))
        else:
            root=roots[s["scope"]]
            path=(root/s["path"]).resolve()
            if not path.is_relative_to(root): raise ContractError("PATH_INVALID",s["role"])
            if not path.is_file():
                if s["availability"]=="MISSING": observed[s["role"]]="MISSING"; continue
                raise ContractError("SOURCE_MISSING",s["role"],s["path"])
            actual=hash_file(path)
        if s["availability"]!="PRESENT" or actual != s["sha256"]:
            raise ContractError("SOURCE_MISMATCH",s["role"],"hash RAW divergente")
        observed[s["role"]]=actual
    return observed


def validate_event(value: Any, manifest: dict) -> dict:
    validate_manifest(manifest)
    e=_object(value,"event")
    _keys(e,{"schema","component_version","event_id","group_id","activity_id",
             "revision_id","supersedes_revision_id","question_text","student_turns",
             "kai_declaration","evidence_refs","created_at_utc","response_sha256",
             "source_sha256","rubric_sha256","model_sha256"},set(),"event")
    _schema(e,EVENT_SCHEMA)
    _uuid(e["event_id"],"event_id")
    if e["group_id"] != manifest["group_id"]: raise ContractError("GROUP_MISMATCH","group_id")
    if e["activity_id"] not in ACTIVITIES: raise ContractError("ACTIVITY_UNKNOWN","activity_id")
    _revision(e["revision_id"],"revision_id")
    _revision(e["supersedes_revision_id"],"supersedes_revision_id",nullable=True)
    if e["supersedes_revision_id"] == e["revision_id"]:
        raise ContractError("REVISION_CYCLE","supersedes_revision_id")
    _text(e["question_text"],"question_text")
    turns=e["student_turns"]
    if not isinstance(turns,list) or not 1<=len(turns)<=20:
        raise ContractError("TYPE_INVALID","student_turns","1–20 turnos")
    ids=set()
    for i,raw in enumerate(turns):
        t=_object(raw,f"student_turns[{i}]")
        _keys(t,{"turn_id","text"},set(),f"student_turns[{i}]")
        _id(t["turn_id"],f"student_turns[{i}].turn_id")
        _text(t["text"],f"student_turns[{i}].text")
        if t["turn_id"] in ids: raise ContractError("TURN_DUPLICATE","student_turns")
        ids.add(t["turn_id"])
    declaration=_object(e["kai_declaration"],"kai_declaration")
    _keys(declaration,{"comprension_declarada","reason"},{"actor_label"},"kai_declaration")
    if type(declaration["comprension_declarada"]) is not bool:
        raise ContractError("TYPE_INVALID","kai_declaration.comprension_declarada","booleano")
    if declaration["reason"] is not None: _text(declaration["reason"],"kai_declaration.reason")
    if "actor_label" in declaration: _text(declaration["actor_label"],"kai_declaration.actor_label",max_len=80)
    refs=e["evidence_refs"]
    if not isinstance(refs,list) or len(refs)>50: raise ContractError("TYPE_INVALID","evidence_refs","lista")
    for i,r in enumerate(refs): _id(r,f"evidence_refs[{i}]")
    if len(refs)!=len(set(refs)): raise ContractError("REFERENCE_DUPLICATE","evidence_refs")
    _utc(e["created_at_utc"],"created_at_utc")
    for key in ("response_sha256","source_sha256","rubric_sha256","model_sha256"):
        _sha(e[key],key)
    viewer=next(x for x in manifest["sources"] if x["role"]=="VIEWER_HTML")
    if e["response_sha256"] != response_hash(turns): raise ContractError("HASH_MISMATCH","response_sha256")
    if e["source_sha256"] != manifest_hash(manifest): raise ContractError("SOURCE_MISMATCH","source_sha256")
    if e["rubric_sha256"] != manifest["rubric"]["sha256"]: raise ContractError("RUBRIC_MISMATCH","rubric_sha256")
    if e["model_sha256"] != viewer["sha256"]: raise ContractError("SOURCE_MISMATCH","model_sha256")
    return e


def event_hash(event: dict, manifest: dict) -> str:
    validate_event(event,manifest)
    return hash_canonical(event)  # hash externo; el evento no contiene su hash


def validate_verification(value: Any, *, current_ref: dict | None, legacy: bool) -> dict:
    v=_object(value,"verificacion")
    _keys(v,{"estado","revision_id","response_sha256","source_sha256","rubric_sha256",
             "evaluation_ref","snapshot_refs","reason_code"},set(),"verificacion")
    if v["estado"] not in VERIFICATION_STATES: raise ContractError("STATE_INVALID","verificacion.estado")
    if v["estado"]=="VERIFICADA":
        raise ContractError("VERIFICATION_UNAVAILABLE","verificacion.estado","PED-003/004/005 pendientes")
    if v["evaluation_ref"] is not None:
        raise ContractError("EVALUATION_UNAVAILABLE","verificacion.evaluation_ref","sin evaluador PED-004")
    if v["snapshot_refs"] != []:
        raise ContractError("SNAPSHOT_UNAVAILABLE","verificacion.snapshot_refs","sin colector PED-003")
    if v["reason_code"] is not None: _id(v["reason_code"],"verificacion.reason_code")
    if current_ref is None:
        if any(v[k] is not None for k in ("revision_id","response_sha256","source_sha256","rubric_sha256")):
            raise ContractError("STALE_REVISION","verificacion","sin revisión v2")
        expected="DECLARADA_HEREDADA" if legacy else "SIN_EVALUAR"
        if v["estado"]!=expected: raise ContractError("STATE_INVALID","verificacion.estado",expected)
    else:
        if v["estado"] not in ("EN_REVISION","REFUERZO","DOCENTE_PENDIENTE","INVALIDADA"):
            raise ContractError("STATE_INVALID","verificacion.estado","respuesta pendiente")
        for key in ("revision_id","response_sha256","source_sha256","rubric_sha256"):
            if v[key]!=current_ref[key]: raise ContractError("STALE_REVISION",f"verificacion.{key}")
    return v


def validate_recorrido(value: Any, manifest: dict) -> dict:
    validate_manifest(manifest)
    d=_object(value,"recorrido")
    _keys(d,{"schema","component_version","group_id","alias","manifest_sha256",
             "rubric_sha256","created_at_utc","updated_at_utc","legacy_source","activities"},set(),"recorrido")
    _schema(d,RECORRIDO_SCHEMA)
    if d["group_id"]!=manifest["group_id"]: raise ContractError("GROUP_MISMATCH","group_id")
    _id(d["alias"],"alias")
    _sha(d["manifest_sha256"],"manifest_sha256")
    _sha(d["rubric_sha256"],"rubric_sha256")
    if d["manifest_sha256"]!=manifest_hash(manifest): raise ContractError("SOURCE_MISMATCH","manifest_sha256")
    if d["rubric_sha256"]!=manifest["rubric"]["sha256"]: raise ContractError("RUBRIC_MISMATCH","rubric_sha256")
    _utc(d["created_at_utc"],"created_at_utc"); _utc(d["updated_at_utc"],"updated_at_utc")
    legacy=d["legacy_source"]
    if legacy is not None:
        legacy=_object(legacy,"legacy_source")
        _keys(legacy,{"schema","original_sha256","documentary_integrity"},set(),"legacy_source")
        if legacy["schema"]!="gem-recorrido/1": raise ContractError("SCHEMA_INCOMPATIBLE","legacy_source.schema")
        _sha(legacy["original_sha256"],"legacy_source.original_sha256")
        if legacy["documentary_integrity"] not in ("VALIDA","NO_COMPROBADA"):
            raise ContractError("STATE_INVALID","legacy_source.documentary_integrity")
    activities=_object(d["activities"],"activities")
    if set(activities)!=set(ACTIVITIES): raise ContractError("FIELD_MISSING","activities","13 actividades exactas")
    all_event_ids=set(); all_turn_ids=set()
    for step in ACTIVITIES:
        a=_object(activities[step],f"activities.{step}")
        _keys(a,{"estado","current_revision_id","event_refs","legacy_attempts","verificacion"},set(),step)
        if a["estado"] not in LEGACY_STATES: raise ContractError("STATE_INVALID",f"{step}.estado")
        if not isinstance(a["legacy_attempts"],list): raise ContractError("TYPE_INVALID",f"{step}.legacy_attempts")
        if legacy is None and a["legacy_attempts"]:
            raise ContractError("LEGACY_SOURCE_MISSING",step)
        if not isinstance(a["event_refs"],list): raise ContractError("TYPE_INVALID",f"{step}.event_refs")
        refs=a["event_refs"]
        for i,raw in enumerate(refs):
            ref=_object(raw,f"{step}.event_refs[{i}]")
            _keys(ref,{"revision_id","event_id","event_sha256","response_sha256",
                       "source_sha256","rubric_sha256","turn_ids"},set(),f"{step}.event_refs[{i}]")
            if ref["revision_id"]!=f"r{i+1:06d}": raise ContractError("REVISION_INVALID",step,"secuencia sin huecos")
            _uuid(ref["event_id"],f"{step}.event_id")
            if ref["event_id"] in all_event_ids: raise ContractError("EVENT_DUPLICATE",step)
            all_event_ids.add(ref["event_id"])
            for key in ("event_sha256","response_sha256","source_sha256","rubric_sha256"):
                _sha(ref[key],f"{step}.{key}")
            if ref["source_sha256"]!=d["manifest_sha256"] or ref["rubric_sha256"]!=d["rubric_sha256"]:
                raise ContractError("SOURCE_MISMATCH",step,"revisión con fuente/rúbrica diferente")
            if not isinstance(ref["turn_ids"],list) or not ref["turn_ids"]:
                raise ContractError("TYPE_INVALID",f"{step}.turn_ids")
            for turn_id in ref["turn_ids"]:
                _id(turn_id,f"{step}.turn_ids")
                if turn_id in all_turn_ids: raise ContractError("TURN_DUPLICATE",step)
                all_turn_ids.add(turn_id)
        current=refs[-1] if refs else None
        if a["current_revision_id"] != (current["revision_id"] if current else None):
            raise ContractError("STALE_REVISION",f"{step}.current_revision_id")
        validate_verification(a["verificacion"],current_ref=current,
                              legacy=legacy is not None and a["estado"]=="comprendido" and not refs)
    return d


def can_advance_v2(recorrido: dict, manifest: dict, activity_id: str) -> dict:
    """Interfaz preparatoria: no se integra en siguiente/reanudar antes de PED-005."""
    validate_recorrido(recorrido,manifest)
    if activity_id not in ACTIVITIES: raise ContractError("ACTIVITY_UNKNOWN","activity_id")
    return {"allowed":False,"reason_code":"PED_005_NOT_ACTIVE",
            "verification_state":recorrido["activities"][activity_id]["verificacion"]["estado"]}


def future_component_envelope(schema: str, group_id: str, activity_id: str,
                              revision_id: str, input_refs: list[str]) -> dict:
    if schema not in FUTURE_SCHEMAS: raise ContractError("SCHEMA_INCOMPATIBLE","schema")
    if group_id!="G03": raise ContractError("GROUP_MISMATCH","group_id")
    if activity_id not in ACTIVITIES: raise ContractError("ACTIVITY_UNKNOWN","activity_id")
    _revision(revision_id,"revision_id")
    if not isinstance(input_refs,list): raise ContractError("TYPE_INVALID","input_refs")
    for r in input_refs: _id(r,"input_refs")
    return {"schema":schema,"component_version":COMPONENT_VERSION,"group_id":group_id,
            "activity_id":activity_id,"revision_id":revision_id,"input_refs":input_refs,
            "issued_at_utc":utc_now(),"status":"NOT_IMPLEMENTED",
            "errors":[{"code":FUTURE_SCHEMAS[schema]}]}


def validate_future_component_envelope(value: Any) -> dict:
    d=_object(value,"future_component")
    _keys(d,{"schema","component_version","group_id","activity_id","revision_id",
             "input_refs","issued_at_utc","status","errors"},set(),"future_component")
    if d["schema"] not in FUTURE_SCHEMAS: raise ContractError("SCHEMA_INCOMPATIBLE","schema")
    _schema(d,d["schema"])
    if d["group_id"]!="G03" or d["activity_id"] not in ACTIVITIES:
        raise ContractError("GROUP_MISMATCH","group_id/activity_id")
    _revision(d["revision_id"],"revision_id"); _utc(d["issued_at_utc"],"issued_at_utc")
    if d["status"]!="NOT_IMPLEMENTED" or d["errors"]!=[{"code":FUTURE_SCHEMAS[d["schema"]]}]:
        raise ContractError("COMPONENT_UNAVAILABLE","status","sin resultados PED-003/004")
    if not isinstance(d["input_refs"],list): raise ContractError("TYPE_INVALID","input_refs")
    for r in d["input_refs"]: _id(r,"input_refs")
    return d
