"""Cotejo documental del sustento económico por operación; no evalúa comprensión."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

REQUIRED = ("problema", "alternativas", "comparacion", "restricciones", "recomendacion", "condicion")

def configuracion(root: Path) -> dict:
    group=json.loads((root/"grupo.json").read_text(encoding="utf-8"))
    code=group.get("grupo")
    if code not in {f"G{n:02d}" for n in range(1,7)}:
        raise ValueError("Identificador de operación inválido")
    history=f"datos/{code}_RESULTADOS_HISTORICOS.json"
    viewer=f"visor/{code}_S11_S12_VISOR_INTERACTIVO.html"
    s04=f"visor/{code}_S04_BASE_FUENTE.json"
    for name in (history,viewer,s04,"plantilla/GEM_KAI_LAB01_Plantilla_Grupal_v2.xlsx"):
        if not (root/name).is_file(): raise FileNotFoundError(name)
    return {"grupo":code,"operacion":group["operacion"],"historico":history,
            "visor":viewer,"s04":s04,"fuente_bloque":viewer+"#case_data"}

def fuente_bloque(root: Path) -> str:
    return configuracion(root)["fuente_bloque"]

def _hash_sustento(value: dict | None) -> str:
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()

def huellas(root: Path, ruta: str) -> dict[str,str]:
    cfg=configuracion(root)
    paths=["grupo.json",cfg["visor"]] if ruta=="S11_S12_BLOQUE" else ["grupo.json",cfg["historico"]]
    if ruta=="OPERACIONAL_S04": paths.append(cfg["s04"])
    return {name:sha256((root/name).read_bytes()).hexdigest() for name in paths}

def vigencia(root: Path, acuerdo: dict | None) -> dict:
    if not acuerdo: return {"estado":"INSUFICIENTE","motivos":["No existe acuerdo final"],"kpi":[]}
    saved=acuerdo.get("calidad_gerencial")
    if not saved: return calidad(root,acuerdo["texto"],None)
    if saved["estado"]!="PREPARADA_PARA_REVISION_DOCENTE": return saved
    route=saved.get("ruta")
    if (saved.get("propuesta_sha256")!=sha256(acuerdo["texto"].encode("utf-8")).hexdigest()
            or saved.get("sustento_sha256")!=_hash_sustento(acuerdo.get("sustento"))
            or saved.get("grupo")!=configuracion(root)["grupo"]
            or saved.get("propuesta_id")!=acuerdo.get("propuesta_id")
            or saved.get("revision_acuerdo")!=acuerdo.get("revision_acuerdo")
            or saved.get("fuentes_sha256")!=huellas(root,route)):
        return {"estado":"PENDIENTE_SUSTENTO","motivos":["Cambió propuesta, revisión o fuente económica; revalidar acuerdo vigente"],
                "kpi":[],"ruta":route}
    return saved

def _decimal(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite(): raise ValueError("KPI no finito")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("KPI numérico inválido") from exc

def _decimal_s04(value):
    """Interpreta solo el formato decimal español usado en la guía S04."""
    if isinstance(value,str) and "," in value:
        return _decimal(value.replace(".", "").replace(",", "."))
    if isinstance(value,str) and value.count(".")==1 and len(value.rsplit(".",1)[1])==3:
        return _decimal(value.replace(".", ""))
    return _decimal(value)

def fuentes(root: Path) -> list[dict]:
    """Matriz de cifras existentes; conserva etapa, estado y escala originales."""
    cfg=configuracion(root); source=cfg["historico"]
    data=json.loads((root/source).read_text(encoding="utf-8"))
    if data.get("grupo")!=cfg["grupo"] or data.get("operacion")!=cfg["operacion"]:
        raise ValueError("Histórico incompatible con la operación")
    rows=[]
    for item in data["registros"]:
        if item.get("grupo")!=cfg["grupo"] or item.get("operacion")!=cfg["operacion"]:
            raise ValueError("KPI pertenece a otra operación")
        rows.append({"codigo":item["codigo"],"valor":item.get("valor"),"unidad":item.get("unidad"),
            "grupo":item["grupo"],"etapa":item.get("etapa"),"escenario":item.get("alternativa"),
            "periodo":item.get("periodo"),"fuente":source+" :: "+str(item.get("archivo_original"))+" :: "+str(item.get("hoja"))+"!"+str(item.get("celda")),
            "estado_fuente":item.get("estado_validacion"),"metodo":item.get("formula") or item.get("ubicacion_html") or "FUENTE_DECLARADA",
            "limites":item.get("observaciones_comparabilidad")})
    return rows

def bloque(root: Path, block_id: str, estado: str) -> dict:
    if estado not in ("YA_EXTRAIDO", "MINADO_OPCIONAL"):
        raise ValueError("Estado de extracción inválido")
    from continuidad_gem import datos_visor
    cfg=configuracion(root); model=datos_visor(root)
    if not block_id.startswith(cfg["grupo"]+"_"):
        raise ValueError("Bloque pertenece a otra operación")
    row=next((r for r in model["blocks"] if r[0]==block_id),None)
    if row is None: raise ValueError("Bloque fuera del modelo de esta operación")
    p=model["parameters"]
    if row[10] is None:
        return {"estado":"NO_EVALUABLE","bloque_id":block_id,"razon":"Recuperación proxy ausente; no sustituir por cero"}
    tonnes=_decimal(row[8]); grade=_decimal(row[7]); recovery=_decimal(row[10])
    copper=tonnes*grade/100; recovered=copper*recovery; payable=recovered*_decimal(p["payable_fraction"])
    revenue=payable*(_decimal(p["price_cu_usd_t"])-_decimal(p["selling_deduction_usd_per_t_payable_cu"]))
    process=tonnes*_decimal(p["process_cost_usd_t_feed_by_domain"][row[9]])
    mine=tonnes*_decimal(p["mine_cost_usd_t_rock"]); disposal=tonnes*_decimal(p["disposal_cost_usd_t"])
    values={"TONELAJE_T":(tonnes,"t roca"),"LEY_PCT_CU":(grade,"% Cu"),
        "RECUPERACION_PROXY":(recovery,"fracción"),"CU_PAGABLE_T":(payable,"t Cu"),
        "INGRESO_USD":(revenue,"US$"),"COSTO_PROCESO_USD":(process,"US$"),
        "VALOR_PROCESAR_YA_MINADO_USD":(revenue-process,"US$"),
        "VALOR_BOTADERO_YA_MINADO_USD":(-disposal,"US$"),
        "VALOR_EXTRAER_PROCESAR_USD":(revenue-process-mine,"US$"),
        "VALOR_NO_EXTRAER_USD":(Decimal(0),"US$")}
    return {"estado":"SUPUESTO_DIDACTICO","bloque_id":block_id,"dominio":row[9],"banco":row[3],
            "estado_extraccion":estado,"valores":values,"fuente":cfg["fuente_bloque"],
            "periodo":"bloque; escenario base D08", "limite":p["value_basis"]}

def calidad(root: Path, propuesta: str, sustento: dict | None) -> dict:
    """Valida fuente y procedencia; nunca aprueba la semántica del equipo."""
    if re.search(r"\b(?:aprobada|aprobado|verificada|verificado|calificada|calificado)\s+(?:por\s+(?:el\s+)?docente|acad[eé]micamente)\b",propuesta,re.I):
        raise ValueError("Aprobación académica declarada sin evaluación docente independiente")
    if not sustento:
        return {"estado":"INSUFICIENTE" if len(propuesta.strip())<120 else "PENDIENTE_SUSTENTO",
                "motivos":["Sin sustento económico estructurado contrastado"],"kpi":[]}
    if not isinstance(sustento,dict) or set(sustento)!={"ruta",*REQUIRED,"kpi","bloque_id","estado_extraccion"}:
        raise ValueError("Esquema de sustento incompleto o con campos ajenos")
    for field in REQUIRED:
        value=sustento[field]
        if not isinstance(value,str) or not value.strip() or value not in propuesta:
            raise ValueError(f"{field}: conservar texto literal de la propuesta")
    indicators=sustento["kpi"]
    if not isinstance(indicators,list) or len(indicators)<2 or len({x.get("codigo") for x in indicators})<2:
        return {"estado":"PENDIENTE_SUSTENTO","motivos":["Se requieren dos KPI distintos"],"kpi":[]}
    route=sustento["ruta"]; checked=[]
    if route=="S11_S12_BLOQUE":
        model=bloque(root,sustento["bloque_id"],sustento["estado_extraccion"])
        if model["estado"]=="NO_EVALUABLE":
            return {"estado":"PENDIENTE_SUSTENTO","motivos":[model["razon"]],"kpi":[]}
        allowed=("VALOR_PROCESAR_YA_MINADO_USD","VALOR_BOTADERO_YA_MINADO_USD") if model["estado_extraccion"]=="YA_EXTRAIDO" else ("VALOR_EXTRAER_PROCESAR_USD","VALOR_NO_EXTRAER_USD")
        for item in indicators:
            code=item.get("codigo")
            if code not in allowed: raise ValueError("KPI incompatible con estado de extracción o escenario D08")
            value,unit=model["valores"][code]
            if (abs(_decimal(item.get("valor"))-value)>Decimal("0.01") or item.get("unidad")!=unit
                    or item.get("fuente")!=model["fuente"] or item.get("escenario")!=model["estado_extraccion"]
                    or item.get("periodo")!=model["periodo"]):
                raise ValueError("KPI no coincide con fuente, unidad, escenario o periodo del bloque")
            interpretation=item.get("interpretacion")
            if not isinstance(interpretation,str) or interpretation not in propuesta:
                raise ValueError("Interpretación del KPI ausente de la propuesta")
            checked.append({**item,"valor_fuente":str(value),"estado_fuente":"SUPUESTO_DIDACTICO","bloque_id":model["bloque_id"],"limite":model["limite"]})
    elif route=="OPERACIONAL_S04":
        if sustento["bloque_id"] is not None or sustento["estado_extraccion"] is not None:
            raise ValueError("No mezclar bloque D08 con la línea base S04")
        rows={r["codigo"]:r for r in fuentes(root)}
        for item in indicators:
            source=rows.get(item.get("codigo"))
            if (not source or source["etapa"]!="S04_R11_GUIA" or
                item.get("codigo") not in {f"S04_KPI_{n:02d}" for n in range(1,6)}):
                raise ValueError("KPI S04 sin cifra numérica comparable en la línea base")
            if (abs(_decimal_s04(item.get("valor"))-_decimal_s04(source["valor"]))>Decimal("0.000001")
                    or any(item.get(k)!=source[k] for k in ("unidad","fuente","periodo"))
                    or item.get("escenario")!=source["escenario"]):
                raise ValueError("KPI S04 no coincide con su fuente")
            if not isinstance(item.get("interpretacion"),str) or item["interpretacion"] not in propuesta:
                raise ValueError("Interpretación del KPI ausente de la propuesta")
            checked.append({**item,"valor_fuente":str(source["valor"]),"estado_fuente":source["estado_fuente"],"limite":source["limites"]})
        return {"estado":"PENDIENTE_SUSTENTO", "motivos":["S04 solo aporta Base histórica; falta una fuente homogénea para comparar alternativas"],
                "kpi":checked,"ruta":route,"fuentes_sha256":huellas(root,route)}
    elif route=="OPERACIONAL_T2_R11":
        if sustento["bloque_id"] is not None or sustento["estado_extraccion"] is not None:
            raise ValueError("No mezclar bloque D08 con alternativas T2/R11")
        rows={r["codigo"]:r for r in fuentes(root)}
        selected=[]
        for item in indicators:
            source=rows.get(item.get("codigo"))
            if (not source or not source["etapa"].startswith("T2")
                    or source["estado_fuente"] not in ("VERIFICADO","VERIFICADO_EN_FCF_ORIGINAL","DERIVADO_R11")):
                raise ValueError("KPI sin fuente T2/R11 contrastada")
            if (abs(_decimal(item.get("valor"))-_decimal(source["valor"]))>Decimal("0.000001")
                    or any(item.get(k)!=source[k] for k in ("unidad","fuente","periodo"))
                    or item.get("escenario")!=source["escenario"]):
                raise ValueError("KPI T2/R11 no coincide con su fuente")
            if not isinstance(item.get("interpretacion"),str) or item["interpretacion"] not in propuesta:
                raise ValueError("Interpretación del KPI ausente de la propuesta")
            selected.append(source);checked.append({**item,"valor_fuente":str(source["valor"]),"estado_fuente":source["estado_fuente"],"limite":source["limites"]})
        if len({r["escenario"] for r in selected})!=1:
            raise ValueError("Alternativas T2 incompatibles")
    else:
        raise ValueError("Ruta económica no reconocida")
    return {"estado":"PREPARADA_PARA_REVISION_DOCENTE","motivos":["Fuente y estructura cotejadas; pertinencia conceptual pendiente del docente"],
            "kpi":checked,"ruta":route,"fuentes_sha256":huellas(root,route),
            "propuesta_sha256":sha256(propuesta.encode("utf-8")).hexdigest(),
            "sustento_sha256":_hash_sustento(sustento),"grupo":configuracion(root)["grupo"]}
