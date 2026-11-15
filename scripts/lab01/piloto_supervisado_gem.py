"""Proyección conservadora del piloto sobre recorrido v1.

Los estados académicos siguen el vocabulario de GEM-PED-002. Este módulo no
emite VERIFICADA: la evaluación independiente todavía no existe.
"""
from __future__ import annotations

from copy import deepcopy

from gem_contratos_ped import LEGACY_STATES, VERIFICATION_STATES
from gem_integridad import sha_bytes

MODO = "PILOTO_DOCENTE_SUPERVISADO"
PENDIENTE = "PENDIENTE_DOCENTE"
VISUAL_PENDIENTE = "EVIDENCIA_VISUAL_NO_VERIFICADA"
INDIVIDUAL_SCHEMA = "gem-individual/2"
GROUP_SCHEMA = "gem-grupal-entrega/2"
FORMATIVE_STATES = LEGACY_STATES
ACADEMIC_STATES = VERIFICATION_STATES


def revision_ref(event: dict) -> dict:
    """Identidad local de la respuesta literal vigente; no autentica al actor."""
    return {"turno_id": event["turno_id"],
            "entrada_sha256": event["entrada_sha256"],
            "respuesta_sha256": sha_bytes(event["respuesta"].encode("utf-8"))}


def nueva_verificacion(event: dict) -> dict:
    state = "REFUERZO" if event["estado"] == "requiere_refuerzo" else "EN_REVISION"
    return {"estado": state, "revision_ref": revision_ref(event),
            "reason_code": "VALIDACION_INDEPENDIENTE_PENDIENTE",
            "evaluation_ref": None, "snapshot_refs": []}


def validar_recorrido_piloto(state: dict, pasos: tuple[str, ...]) -> None:
    """Rechaza etiquetas de certificación inyectadas y referencias obsoletas."""
    if state.get("schema") != "gem-recorrido/1" or set(state.get("actividades", {})) != set(pasos):
        raise ValueError("Recorrido piloto incompatible")
    if state.get("modo", MODO) != MODO:
        raise ValueError("Modo de recorrido desconocido")
    for step in pasos:
        activity = state["actividades"][step]
        if activity.get("estado") not in FORMATIVE_STATES:
            raise ValueError(f"Estado formativo desconocido: {step}")
        attempts = activity.get("intentos")
        if not isinstance(attempts, list):
            raise ValueError(f"Intentos inválidos: {step}")
        if attempts and attempts[-1].get("estado") != activity["estado"]:
            raise ValueError(f"Estado formativo no coincide con el último intento: {step}")
        if activity["estado"] == "comprendido" and not attempts:
            raise ValueError(f"Cierre formativo sin intento real: {step}")
        verification = activity.get("verificacion")
        if verification is None:
            continue  # expediente v1: declaración heredada, nunca verificación
        if not isinstance(verification, dict) or set(verification) != {
                "estado", "revision_ref", "reason_code", "evaluation_ref", "snapshot_refs"}:
            raise ValueError(f"Contrato de verificación inválido: {step}")
        if verification["estado"] not in ACADEMIC_STATES or verification["estado"] == "VERIFICADA":
            raise ValueError(f"Verificación académica no disponible: {step}")
        if verification["evaluation_ref"] is not None or verification["snapshot_refs"] != []:
            raise ValueError(f"Evaluación o snapshot independientes no disponibles: {step}")
        if attempts:
            last = attempts[-1]
            expected = nueva_verificacion(last)
            if verification != expected:
                raise ValueError(f"Verificación ligada a revisión antigua o alterada: {step}")
        elif verification != {"estado": "SIN_EVALUAR", "revision_ref": None,
                               "reason_code": "SIN_RESPUESTA", "evaluation_ref": None,
                               "snapshot_refs": []}:
            raise ValueError(f"Verificación sin respuesta incoherente: {step}")


def proyectar(state: dict, pasos: tuple[str, ...], *, integridad: str = "NO_EVALUADA",
              publicacion: str = "NO_VERIFICADA") -> dict:
    """Calcula dimensiones desde el recorrido; ignora toda aprobación declarada."""
    validar_recorrido_piloto(state, pasos)
    activities = {}
    completed = 0
    for step in pasos:
        item = state["actividades"][step]
        attempts = item["intentos"]
        closed = item["estado"] == "comprendido" and bool(attempts)
        completed += closed
        verification = item.get("verificacion")
        if verification is not None:
            academic = verification["estado"]
            reference = deepcopy(verification["revision_ref"])
        elif closed:
            academic, reference = "DECLARADA_HEREDADA", None
        elif attempts and item["estado"] == "requiere_refuerzo":
            academic, reference = "REFUERZO", None
        elif attempts:
            academic, reference = "EN_REVISION", None
        else:
            academic, reference = "SIN_EVALUAR", None
        activities[step] = {"cierre_formativo": "DECLARADO" if closed else "PENDIENTE",
                            "verificacion_estado": academic, "revision_ref": reference}
    return {"schema": "gem-piloto-estado/1", "modo": MODO,
            "grupo": state["grupo"], "alias": state["alias"],
            "recorrido_revision": state["revision"], "cierres_formativos": completed,
            "actividades": activities,
            "dimensiones": {"INTEGRIDAD_DOCUMENTAL": integridad,
                           "COMPLETITUD_FORMATIVA": "COMPLETA" if completed == len(pasos) else "EN_CURSO",
                           "VERIFICACION_ACADEMICA": PENDIENTE,
                           "EVIDENCIA_VISUAL": VISUAL_PENDIENTE,
                           "PUBLICACION_REMOTA": publicacion,
                           "CALIFICACION_DOCENTE": "NO_EMITIDA"}}
