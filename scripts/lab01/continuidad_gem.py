"""Ruta académica obligatoria posterior al Lab01; no altera su esquema v2."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

from gem_integridad import (atomico, bloqueo, json_bytes, nuevo, ruta_local,
                            sha_bytes, sha_file, texto)
from kai_lab01_v2 import SESSION_DATE, _first_pending, review
from lab01_common_v2 import _alias, _config, _read_json
from piloto_supervisado_gem import MODO, nueva_verificacion, proyectar, validar_recorrido_piloto


PASOS=tuple(f'P09.{i}' for i in range(1,7))+tuple(f'P10.{i}' for i in range(1,7))+('DECISION_FINAL',)
FILE='recorrido_gem.json'


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def catalogo(root: Path) -> dict:
    data=_read_json(root/'docs/ACTIVIDADES_GEM.json')
    if set(data)!=set(PASOS): raise ValueError('Catálogo de actividades incompleto')
    return data


def contexto(root: Path, alias: str):
    config=_config(root); alias=_alias(alias)
    folder=root/'trabajos'/alias/SESSION_DATE
    state=_read_json(folder/'progreso.json')
    if (state.get('version')!=2 or state.get('grupo')!=config['grupo']
            or state.get('alias')!=alias or state.get('operacion')!=config['operacion']
            or state.get('fecha')!=SESSION_DATE):
        raise ValueError('Identidad de progreso incompatible con grupo/alias')
    book=folder/state['excel']
    expected=f"GEM_KAI_LAB01_{config['grupo']}_{alias}_Individual_{SESSION_DATE}.xlsx"
    if state['excel']!=expected or not book.is_file(): raise ValueError('Excel individual incorrecto')
    if review(folder)['identidad_excel']!='coincide': raise ValueError('Identidad Excel incoherente')
    return folder,state,config


def vacio(config: dict, alias: str) -> dict:
    return {'schema':'gem-recorrido/1','grupo':config['grupo'],'operacion':config['operacion'],
            'alias':alias,'revision':0,'anterior_sha256':None,'creado_utc':ahora(),'modo':MODO,
            'actividades':{s:{'estado':'pendiente','intentos':[]} for s in PASOS},
            'limite':'Evaluación formativa declarada por tutor; no nota ni aprobación docente.'}


def validar_cadena(state: dict, snapshots: dict[str,bytes]) -> None:
    if state.get('schema')!='gem-recorrido/1' or set(state.get('actividades',{}))!=set(PASOS):
        raise ValueError('Esquema de recorrido inválido')
    n=state.get('revision')
    if not isinstance(n,int) or n<0: raise ValueError('Revisión inválida')
    if n==0:
        if state.get('anterior_sha256') is not None: raise ValueError('Cadena inicial incoherente')
        return
    expected=json_bytes(state)
    for revision in range(n,0,-1):
        key=f'revisiones_gem/{revision:06d}.json'
        raw=snapshots.get(key)
        if raw!=expected: raise ValueError(f'Revisión alterada o ausente: {key}')
        current=json.loads(raw)
        if current.get('revision')!=revision: raise ValueError('Número de revisión incoherente')
        previous=current.get('anterior_sha256')
        if revision==1:
            if previous is not None: raise ValueError('Origen de cadena incoherente')
        else:
            expected=snapshots.get(f'revisiones_gem/{revision-1:06d}.json')
            if expected is None or sha_bytes(expected)!=previous: raise ValueError('Cadena de integridad rota')


def cargar(folder: Path, config: dict, alias: str) -> dict:
    recuperar(folder)
    path=folder/FILE
    if not path.exists(): return vacio(config,alias)
    state=_read_json(path)
    if any(state.get(k)!=v for k,v in {'grupo':config['grupo'],'operacion':config['operacion'],'alias':alias}.items()):
        raise ValueError('Recorrido de otro alumno/grupo')
    snapshots={f'revisiones_gem/{p.name}':p.read_bytes() for p in (folder/'revisiones_gem').glob('*.json')}
    validar_cadena(state,snapshots)
    validar_recorrido_piloto(state,PASOS)
    return state


def guardar(folder: Path, state: dict) -> dict:
    validar_recorrido_piloto(state,PASOS)
    value=deepcopy(state)
    old=folder/FILE
    value['anterior_sha256']=sha_file(old) if old.exists() else None
    value['revision']+=1; value['actualizado_utc']=ahora()
    transaction={'schema':'gem-transaccion/1','anterior_sha256':value['anterior_sha256'],
                 'siguiente':value}
    nuevo(folder/'transaccion_gem.json',json_bytes(transaction))
    nuevo(folder/f"revisiones_gem/{value['revision']:06d}.json",json_bytes(value))
    # El head es el único reemplazo. Una revisión huérfana por fallo se preserva.
    atomico(old,value)
    if _read_json(old)!=value: raise RuntimeError('No se confirmó el recorrido')
    (folder/'transaccion_gem.json').unlink()
    return value


def recuperar(folder: Path) -> None:
    pending=folder/'transaccion_gem.json'
    if not pending.exists(): return
    transaction=_read_json(pending)
    if transaction.get('schema')!='gem-transaccion/1': raise ValueError('Transacción desconocida; preservar para revisión')
    value=transaction['siguiente']; head=folder/FILE; raw=json_bytes(value)
    validar_recorrido_piloto(value,PASOS)
    current=sha_file(head) if head.exists() else None
    if current not in (transaction.get('anterior_sha256'),sha_bytes(raw)):
        raise ValueError('Conflicto de recuperación; no se sobrescribe el recorrido')
    revision=folder/f"revisiones_gem/{value['revision']:06d}.json"
    if revision.exists():
        if revision.read_bytes()!=raw: raise ValueError('Revisión pendiente divergente; preservar')
    else: nuevo(revision,raw)
    snapshots={f'revisiones_gem/{p.name}':p.read_bytes() for p in (folder/'revisiones_gem').glob('*.json')}
    validar_cadena(value,snapshots)
    atomico(head,value); pending.unlink()


def siguiente(state: dict) -> str:
    # Sólo secuencia didáctica: comprendido es cierre formativo declarado en v1.
    return next((s for s in PASOS if state['actividades'][s]['estado']!='comprendido'),'ENTREGA_INDIVIDUAL')


def reanudar(root: Path, alias: str) -> dict:
    folder,lab,config=contexto(root,alias)
    with bloqueo(folder): state=cargar(folder,config,lab['alias'])
    pending=_first_pending(lab)
    step=siguiente(state) if pending=='terminado' else f'LAB01/{pending}'
    delivery='PENDIENTE_VERIFICACION_GITHUB'
    fingerprints={'recorrido':sha_file(folder/FILE) if (folder/FILE).exists() else None,
                  'progreso':sha_file(folder/'progreso.json'),'excel':sha_file(folder/lab['excel'])}
    if step=='ENTREGA_INDIVIDUAL':
        for path in sorted((folder/'despedidas_gem').glob('*.json')):
            closed=_read_json(path)
            if (closed.get('estado')=='RECORRIDO_INDIVIDUAL_CERRADO' and closed.get('huellas')==fingerprints
                    and closed.get('publicacion',{}).get('estado')=='PUBLICADO_GITHUB_VERIFICADO'):
                # El recibo guardado localmente puede alterarse. Reanudar no
                # consulta la red: exige otra verificación con despedir.
                delivery='CIERRE_LOCAL_PREVIO; REVERIFICAR_RECIBO_REMOTO'
                break
    last=[]
    if step in PASOS: last=state['actividades'][step]['intentos']
    projection=proyectar(state,PASOS,publicacion='NO_VERIFICADA')
    return {'grupo':config['grupo'],'alias':lab['alias'],'etapa_actual':step,
            'revision':state['revision'],'comprendidos':sum(v['estado']=='comprendido' for v in state['actividades'].values()),
            'modo':MODO,'cierres_formativos':projection['cierres_formativos'],
            'dimensiones':projection['dimensiones'],
            'ultima_respuesta':last[-1] if last else None,
            'siguiente_pregunta':(last[-1].get('proxima_pregunta') if last else catalogo(root)[step]['pregunta']) if step in PASOS else None,
            'entrega':delivery,'calificacion':'NO_EMITIDA'}


def evidencia(root: Path, raw: dict) -> dict:
    if not isinstance(raw,dict) or set(raw)-{'ruta','panel','observacion','escenario','sha256','algoritmo'}:
        raise ValueError('Campos inesperados en evidencia; no guardar conversaciones ni datos ajenos')
    item=deepcopy(raw)
    path=ruta_local(root,item.get('ruta',''))
    # Solo fuentes del propio caso; nunca fichas privadas de otro alumno.
    group=_config(root)['grupo']
    allowed=(path==root.resolve()/f'visor/{group}_S11_S12_VISOR_INTERACTIVO.html'
             or path==root.resolve()/f'datos/{group}_RESULTADOS_HISTORICOS.json'
             or path==root.resolve()/'docs/CM03_HECHO_HISTORICO.md')
    if not allowed or not path.is_file(): raise ValueError('Fuente ajena al caso o no disponible')
    item['panel']=texto(item.get('panel'),'panel',limit=100)
    item['observacion']=texto(item.get('observacion'),'observación real del estudiante')
    scene=item.get('escenario',{})
    if not isinstance(scene,dict): raise ValueError('Escenario debe ser objeto')
    if set(scene)-{'precio','rec','cp','variable','momento','bloque_id','banco','base_s12','dominio','estado_extraccion'}:
        raise ValueError('Campos inesperados en escenario')
    # Huella LF explícita para documentos versionados, resistente a core.autocrlf.
    item['sha256']=sha_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
    item['algoritmo']='SHA256_LF'; item['escenario']=scene
    return item


def sensibilidad(attempts: list[dict]) -> None:
    found=set(); predictions={}
    for event in attempts:
        for evidence in event['evidencias']:
            scene=evidence.get('escenario',{}); variable=scene.get('variable')
            if variable not in ('precio','rec','cp'): continue
            numbers=tuple(scene.get(k) for k in ('precio','rec','cp'))
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in numbers):
                raise ValueError('Sensibilidad exige precio, rec y cp positivos y explícitos')
            baseline=(6000,1,1); changed=[k for k,a,b in zip(('precio','rec','cp'),numbers,baseline) if a!=b]
            ranges=((3500,8500,100),(.75,1.15,.025),(.65,1.45,.05))
            if any(x<low-1e-9 or x>high+1e-9 or abs((x-low)/stride-round((x-low)/stride))>1e-7
                   for x,(low,high,stride) in zip(numbers,ranges)):
                raise ValueError('Escenario fuera de los rangos/pasos de los controles S11')
            if changed!=[variable]: raise ValueError('Cambiar una sola variable por ciclo de S11')
            key=(variable,numbers)
            if scene.get('momento')=='prediccion': predictions[key]=event['turno_id']
            elif scene.get('momento')=='observacion' and key in predictions and predictions[key]!=event['turno_id']:
                found.add(variable)
    if found!={'precio','rec','cp'}:
        raise ValueError('P09.4 requiere predicción y contraste posterior de precio, recuperación y procesamiento')


def validar_comprension(spec: dict, attempts: list[dict], event: dict):
    if not event.get('confirmado') or event.get('dificultad'):
        raise ValueError('Comprensión requiere comprobación formativa y resolver la dificultad pendiente')
    if len(attempts)<2 or len({a['respuesta'].casefold() for a in attempts})<2:
        raise ValueError('Se requiere aplicación y comprobación en dos turnos distintos; repetir no basta')
    if len({a['pregunta'].casefold() for a in attempts})<2:
        raise ValueError('La comprobación debe plantear una pregunta de aplicación diferente')
    for field in ('interpretacion','conclusion'):
        texto(event.get(field),field)
    if not event['evidencias']: raise ValueError('Falta fuente y observación de evidencia consultada')
    evaluation=event.get('evaluacion',{})
    if evaluation.get('evaluador') not in ('kai','docente'): raise ValueError('Identificar evaluador formativo')
    texto(evaluation.get('razon'),'justificación de evaluación')
    quotes=evaluation.get('criterios',{})
    if set(quotes)!=set(spec['criterios']): raise ValueError('Faltan criterios sustantivos de comprensión')
    for key,quote in quotes.items():
        quote=texto(quote,f'extracto {key}',limit=3000)
        if not any(quote in a['respuesta'] for a in attempts):
            raise ValueError('El criterio debe citar palabras reales del alumno en este paso')
        # La longitud de la cita no mide la calidad de la explicación completa.
        # El cierre es formativo; la comprensión académica queda pendiente.
    evaluation['tipo']='JUICIO_FORMATIVO_DECLARADO; REQUIERE_REVISION_HUMANA'


def registrar(root: Path, alias: str, raw: dict) -> dict:
    allowed={'actividad','turno_id','pregunta','respuesta','interpretacion','conclusion','dificultad',
             'estado','evidencias','evaluacion','confirmado','proxima_pregunta'}
    if not isinstance(raw,dict) or set(raw)-allowed: raise ValueError('Evento fuera del esquema; no guardar datos adicionales')
    if set(raw.get('evaluacion',{}))-{'criterios','razon','evaluador'}:
        raise ValueError('Evaluación fuera del esquema')
    folder,lab,config=contexto(root,alias)
    if _first_pending(lab)!='terminado': raise ValueError('Primero completar Laboratorio 01')
    with bloqueo(folder):
        state=cargar(folder,config,lab['alias']); event=deepcopy(raw)
        step=event.get('actividad')
        if step not in PASOS: raise ValueError('Actividad desconocida')
        turn=texto(event.get('turno_id'),'identificador del turno',limit=100)
        for s in PASOS:
            for old in state['actividades'][s]['intentos']:
                if old['turno_id']==turn:
                    # Reintento exactamente idéntico no duplica ni vuelve a escribir.
                    if old.get('entrada_sha256')==sha_bytes(json_bytes(raw)):
                        return {'estado':'YA_REGISTRADO','revision':state['revision'],'proxima_actividad':siguiente(state)}
                    raise ValueError('Turno duplicado con contenido diferente')
        if step!=siguiente(state): raise ValueError(f'Corresponde {siguiente(state)}, no {step}')
        for field in ('pregunta','respuesta'):
            event[field]=texto(event.get(field),field)
        if event['respuesta'].casefold()==event['pregunta'].casefold() or re.fullmatch(r'[\d\s.,%$+\-/]+',event['respuesta']):
            if event.get('estado')=='comprendido': raise ValueError('Copiar la pregunta o un número no acredita comprensión')
        status=event.get('estado')
        if status not in ('en_curso','requiere_refuerzo','comprendido'): raise ValueError('Estado no permitido')
        if status!='comprendido': texto(event.get('proxima_pregunta'),'próxima pregunta de comprobación')
        event['evidencias']=[evidencia(root,e) for e in event.get('evidencias',[])]
        event['dificultad']=event.get('dificultad','')
        attempts=state['actividades'][step]['intentos']+[event]
        if status=='comprendido':
            validar_comprension(catalogo(root)[step],attempts,event)
            validar_visual(root,step,attempts)
            if step=='P09.4': sensibilidad(attempts)
        event['registrado_utc']=ahora(); event['entrada_sha256']=sha_bytes(json_bytes(raw))
        state['modo']=MODO
        state['actividades'][step]={'estado':status,'intentos':attempts,
                                    'verificacion':nueva_verificacion(event)}
        state=guardar(folder,state)
        projection=proyectar(state,PASOS)
        return {'estado':'REGISTRADO','revision':state['revision'],'proxima_actividad':siguiente(state),
                'confirmado_lectura':True,'evaluacion':'FORMATIVA_DECLARADA; NO_CALIFICACION',
                'modo':MODO,'verificacion_academica':projection['dimensiones']['VERIFICACION_ACADEMICA'],
                'evidencia_visual':projection['dimensiones']['EVIDENCIA_VISUAL']}


def datos_visor(root: Path) -> dict:
    group=_config(root)['grupo']; path=root/f'visor/{group}_S11_S12_VISOR_INTERACTIVO.html'
    html=path.read_text(encoding='utf-8')
    match=re.search(r'<script[^>]*id="case_data"[^>]*>(.*?)</script>',html,re.S)
    if not match: raise ValueError('Falta case_data del visor')
    data=json.loads(match.group(1))
    if data.get('group')!=group or len(data.get('blocks',[]))!=9408: raise ValueError('Modelo del grupo incoherente')
    return data


def validar_visual(root: Path,step: str,attempts: list[dict]) -> None:
    spec=catalogo(root)[step]; group=_config(root)['grupo']
    refs=[e for a in attempts for e in a['evidencias'] if e['ruta']==f'visor/{group}_S11_S12_VISOR_INTERACTIVO.html']
    panels={e['panel'] for e in refs}
    required={spec['panel']}
    if step=='P10.4': required|={'fig-tonnage'}
    if not required.issubset(panels): raise ValueError('Falta observación de los paneles requeridos del visor propio')
    html=(root/f'visor/{group}_S11_S12_VISOR_INTERACTIVO.html').read_text(encoding='utf-8')
    if any(f'id="{e["panel"]}"' not in html and f"id='{e['panel']}'" not in html for e in refs):
        raise ValueError('Panel inexistente en el visor')
    if step.startswith('P10.'):
        data=datos_visor(root)
        if step in ('P10.2','P10.3','P10.6'):
            blocks={row[0] for row in data['blocks']}
            if not any(e['panel']=='block-detail' and e['escenario'].get('bloque_id') in blocks for e in refs):
                raise ValueError('Registrar bloque real del propio grupo')
        if step=='P10.4' and not any(e['panel']=='fig-bank' and isinstance(e['escenario'].get('banco'),int)
                                       and not isinstance(e['escenario'].get('banco'),bool)
                                       and 0<=e['escenario']['banco']<=13 for e in refs):
            raise ValueError('Registrar banco observado (0–13)')
        if step in ('P10.2','P10.3','P10.5','P10.6'):
            if not any(e['escenario'].get('precio')==data['parameters']['price_cu_usd_t']
                       and e['escenario'].get('base_s12') is True for e in refs):
                raise ValueError('S12 requiere escenario base explícito; no hereda sensibilidad S11')


def despedir(root: Path, alias: str, sobre: Path, recibo: Path) -> dict:
    from publicacion_gem import verificar_recibo, metadatos_sobre
    from entrega_gem import comprobar_completo
    folder,lab,config=contexto(root,alias)
    state=cargar(folder,config,lab['alias']); comprobar_completo(root,folder,lab,state)
    result=verificar_recibo(root,sobre,recibo)
    metadata=metadatos_sobre(root,sobre)
    attestation=folder/'sobres_verificados_gem'/f"{metadata['entrega_id']}-{sha_file(sobre)}.json"
    if not attestation.is_file() or _read_json(attestation).get('academico_sha256')!=metadata['academico_sha256']:
        raise ValueError('Falta autenticación local del sobre publicado; verificar con la clave docente antes de la despedida')
    export=folder/'exportaciones_gem'/f"{metadata['entrega_id']}.json"
    receipt=_read_json(export)
    if (receipt.get('recorrido_sha256')!=sha_file(folder/FILE)
            or receipt.get('progreso_sha256')!=sha_file(folder/'progreso.json')
            or receipt.get('excel_sha256')!=sha_file(folder/lab['excel'])
            or receipt.get('paquete_sha256')!=metadata.get('academico_sha256')):
        raise ValueError('La publicación no corresponde a esta versión del trabajo individual')
    message=('Has completado las actividades de preparación en Gerencia Minera; gracias por tu trabajo. '
             'El sobre de esta versión tiene un recibo de publicación verificado y tu equipo puede continuar la integración. '
             'La comprensión académica y la calificación siguen pendientes de revisión docente. '
             'Puedes usar este recorrido para prepararte para el examen.')
    record={'estado':'RECORRIDO_INDIVIDUAL_CERRADO','grupo':config['grupo'],'alias':lab['alias'],
            'publicacion':result,'mensaje':message,'cerrado_utc':ahora(),'modo':MODO,
            'dimensiones':proyectar(state,PASOS,publicacion='RECIBO_VERIFICADO')['dimensiones'],
            'huellas':{'recorrido':sha_file(folder/FILE),'progreso':sha_file(folder/'progreso.json'),
                       'excel':sha_file(folder/lab['excel'])}}
    path=folder/'despedidas_gem'/f"{metadata['entrega_id']}.json"
    if not path.exists(): nuevo(path,json_bytes(record))
    return record


def main():
    p=argparse.ArgumentParser(description='Kai individual — continuidad obligatoria GEM')
    p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2])
    sub=p.add_subparsers(dest='cmd',required=True)
    for cmd in ('reanudar','registrar','exportar','despedir'):
        a=sub.add_parser(cmd); a.add_argument('--alias',required=True)
        if cmd=='registrar': a.add_argument('--entrada',type=Path,required=True)
        if cmd=='exportar': a.add_argument('--salida',type=Path,required=True)
        if cmd=='despedir':
            a.add_argument('--sobre',type=Path,required=True); a.add_argument('--recibo',type=Path,required=True)
    a=p.parse_args()
    try:
        root=a.raiz.resolve()
        if a.cmd=='reanudar': result=reanudar(root,a.alias)
        elif a.cmd=='registrar': result=registrar(root,a.alias,_read_json(a.entrada))
        elif a.cmd=='exportar':
            from entrega_gem import exportar
            result=exportar(root,a.alias,a.salida.resolve())
        else: result=despedir(root,a.alias,a.sobre.resolve(),a.recibo.resolve())
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(f'CONTINUIDAD GEM: {exc}',file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
