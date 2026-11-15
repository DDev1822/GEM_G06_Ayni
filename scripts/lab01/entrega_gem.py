"""Paquetes académicos completos: evidencia privada, manifiesto y revisión docente."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

from continuidad_gem import (FILE, PASOS, cargar, catalogo, contexto, siguiente,
                             validar_cadena, validar_comprension, validar_visual, sensibilidad, evidencia)
from gem_integridad import (bloqueo, escribir_zip, json_bytes, leer_zip, nuevo,
                            ruta_local, sha_bytes, sha_file)
from kai_lab01_v2 import _first_pending, review
from lab01_common_v2 import _config, workbook_values
from piloto_supervisado_gem import (INDIVIDUAL_SCHEMA, MODO, PENDIENTE,
                                   proyectar, validar_recorrido_piloto)


def comprobar_completo(root: Path, folder: Path, lab: dict, recorrido: dict):
    validar_recorrido_piloto(recorrido,PASOS)
    from cierre_grupal_v2 import _validate_student
    _validate_student(root,lab,folder/lab['excel'])
    report=review(folder)
    if (_first_pending(lab)!='terminado' or report['preguntas_con_respuesta']!=6
            or not report['decision_escrita']
            or report['indicadores_con_valor']+report['indicadores_no_disponibles']!=12):
        raise ValueError('Laboratorio 01 incompleto; se conserva la exportación parcial histórica')
    if siguiente(recorrido)!='ENTREGA_INDIVIDUAL': raise ValueError('Faltan actividades S11/S12 o decisión integradora')
    specs=catalogo(root); seen=set()
    for step in PASOS:
        attempts=recorrido['actividades'][step]['intentos']
        if not attempts or attempts[-1].get('estado')!='comprendido': raise ValueError('Paso sin cierre formativo')
        for i,event in enumerate(attempts):
            for e in event['evidencias']:
                checked=evidencia(root,e)
                if checked!=e: raise ValueError('Fuente, huella o esquema de evidencia divergente')
            if event['turno_id'] in seen: raise ValueError('Turno duplicado en evidencia')
            seen.add(event['turno_id'])
            if event.get('estado')=='comprendido':
                validar_comprension(specs[step],attempts[:i+1],event)
        if step=='P09.4': sensibilidad(attempts)
        validar_visual(root,step,attempts)


def informe(root: Path, lab: dict, recorrido: dict, *, piloto: bool = False) -> bytes:
    specs=catalogo(root)
    lines=[f"# Evidencia individual GEM · {lab['grupo']} · {lab['alias']}",
           '', 'Documento académico restringido. Juicios formativos declarados; sin nota automática.',
           '', 'Laboratorio 01: consultar el XLSX y progreso.json originales incluidos.', '']
    if piloto:
        lines += ['Modo: PILOTO_DOCENTE_SUPERVISADO',
                  'Completitud formativa: COMPLETA; verificación académica: PENDIENTE_DOCENTE.',
                  'Evidencia visual: EVIDENCIA_VISUAL_NO_VERIFICADA.',
                  'Publicación remota: NO_VERIFICADA; calificación docente: NO_EMITIDA.',
                  'El estado histórico comprendido sólo registra cierre formativo declarado.', '']
    for step in PASOS:
        data=recorrido['actividades'][step]
        lines += [f"## {step} — {specs[step]['titulo']}",'',f"Estado: {data['estado']}",'']
        if piloto:
            lines += [f"Verificación académica: {proyectar(recorrido,PASOS)['actividades'][step]['verificacion_estado']}",'']
        for event in data['intentos']:
            lines += [f"Turno: {event['turno_id']}",f"Pregunta: {event['pregunta']}",
                      f"Respuesta real: {event['respuesta']}",
                      f"Interpretación registrada: {event.get('interpretacion','')}",
                      f"Conclusión registrada: {event.get('conclusion','')}",
                      f"Dificultad pendiente: {event.get('dificultad','') or 'ninguna declarada'}"]
            for e in event['evidencias']:
                lines += [f"Fuente: {e['ruta']} · {e['panel']} · {e['algoritmo']} {e['sha256']}",
                          f"Escenario: {json.dumps(e['escenario'],ensure_ascii=False)}",f"Observación: {e['observacion']}"]
            if event.get('evaluacion'):
                lines += [f"Evaluación del tutor: {json.dumps(event['evaluacion'],ensure_ascii=False)}"]
            lines += ['']
    return ('\n'.join(lines)+'\n').encode('utf-8')


def excel_continuidad(root: Path, recorrido: dict, *, piloto: bool = False) -> bytes:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb=Workbook(); ws=wb.active; ws.title='S11_S12_Y_DECISION'
    ws.append(['Actividad','Estado','Turno','Pregunta','Respuesta real','Interpretación registrada',
               'Conclusión registrada','Evidencia y escenario','Juicio formativo declarado','Dificultad']
              + (['Verificación académica'] if piloto else []))
    projection=proyectar(recorrido,PASOS) if piloto else None
    for step in PASOS:
        for e in recorrido['actividades'][step]['intentos']:
            ws.append([step,e['estado'],e['turno_id'],e['pregunta'],e['respuesta'],e.get('interpretacion',''),
                       e.get('conclusion',''),json.dumps(e['evidencias'],ensure_ascii=False),
                       json.dumps(e.get('evaluacion',{}),ensure_ascii=False),e.get('dificultad','')]
                      + ([projection['actividades'][step]['verificacion_estado']] if piloto else []))
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s' # nunca ejecutar fórmulas del texto recibido
            cell.alignment=Alignment(wrap_text=True,vertical='top')
    for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='17394D')
    for col in 'ABCDEFGHIJ'+('K' if piloto else ''): ws.column_dimensions[col].width=42 if col in 'DEFGHI' else 24
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    meta=wb.create_sheet('IDENTIDAD_Y_LIMITES')
    for key in ('schema','grupo','operacion','alias','revision','limite'): meta.append([key,str(recorrido[key])])
    if piloto:
        meta.append(['modo',MODO])
        for key,value in projection['dimensiones'].items(): meta.append([key,value])
    for row in meta:
        for cell in row:
            if isinstance(cell.value,str): cell.data_type='s'
    stream=BytesIO(); wb.save(stream)
    check=load_workbook(BytesIO(stream.getvalue()),data_only=False)
    if check['S11_S12_Y_DECISION'].max_row!=sum(len(v['intentos']) for v in recorrido['actividades'].values())+1:
        raise RuntimeError('Excel de continuidad no confirmado')
    return stream.getvalue()


def exportar(root: Path, alias: str, output: Path) -> dict:
    folder,lab,config=contexto(root,alias)
    with bloqueo(folder):
        state=cargar(folder,config,lab['alias']); comprobar_completo(root,folder,lab,state)
        projection=proyectar(state,PASOS,integridad='INTEGRA')
        if output.exists(): raise FileExistsError('La entrega existe; no se sobrescribe')
        if output.resolve().is_relative_to(root.resolve()) and not output.resolve().is_relative_to(folder.resolve()):
            raise ValueError('El ZIP privado debe quedar fuera del repositorio o dentro de trabajos/ del alumno')
        files={lab['excel']:(folder/lab['excel']).read_bytes(),'progreso.json':(folder/'progreso.json').read_bytes(),
               FILE:(folder/FILE).read_bytes(),'INFORME_ACADEMICO.md':informe(root,lab,state,piloto=True),
               'GEM_CONTINUIDAD_ACADEMICA.xlsx':excel_continuidad(root,state,piloto=True),
               'ESTADO_ACADEMICO.json':json_bytes(projection),
               'fuentes/ACTIVIDADES_GEM.json':(root/'docs/ACTIVIDADES_GEM.json').read_bytes(),
               'fuentes/CM03_HECHO_HISTORICO.md':(root/'docs/CM03_HECHO_HISTORICO.md').read_bytes()}
        for n in range(1,state['revision']+1):
            name=f'revisiones_gem/{n:06d}.json'; files[name]=(folder/name).read_bytes()
        if (folder/'decision_lab01_criterios.json').is_file():
            files['decision_lab01_criterios.json']=(folder/'decision_lab01_criterios.json').read_bytes()
        evidence=[]
        for item in state['actividades'].values():
            for event in item['intentos']: evidence+=event['evidencias']
        unique={}
        for e in evidence:
            path=ruta_local(root,e['ruta'])
            if sha_bytes(path.read_bytes().replace(b'\r\n',b'\n'))!=e['sha256']:
                raise ValueError('Una fuente cambió desde la respuesta; revisar sin reescribir evidencias')
            unique[(e['ruta'],e['sha256'])]={'ruta':e['ruta'],'sha256':e['sha256'],'algoritmo':e['algoritmo']}
        files['FUENTES_VERSIONADAS.json']=json_bytes(list(unique.values()))
        receipt={'schema':INDIVIDUAL_SCHEMA,'grupo':config['grupo'],'operacion':config['operacion'],
                 'alias':lab['alias'],'entrega_id':str(uuid.uuid4()),'estado_academico':'PENDIENTE_REVISION_DOCENTE',
                 'modo':MODO,'dimensiones':projection['dimensiones'],
                 'publicacion':'NO_VERIFICADA','evaluacion':'FORMATIVA_DECLARADA; NO_NOTA',
                 'creado_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 'sha256':{n:sha_bytes(v) for n,v in files.items()}}
        files['RECIBO_INDIVIDUAL.json']=json_bytes(receipt)
        # La verificación receptora usa el mismo formato completo, sin modificar el laboratorio.
        escribir_zip(output,files); verificar_paquete(root,output)
        checksum=sha_file(output)
        nuevo(output.with_suffix(output.suffix+'.sha256'),f'{checksum}  {output.name}\n'.encode('ascii'))
        local={'entrega_id':receipt['entrega_id'],'grupo':config['grupo'],'alias':lab['alias'],
               'paquete_sha256':checksum,'recorrido_sha256':sha_file(folder/FILE),
               'progreso_sha256':sha_file(folder/'progreso.json'),'excel_sha256':sha_file(folder/lab['excel'])}
        nuevo(folder/'exportaciones_gem'/f"{receipt['entrega_id']}.json",json_bytes(local))
        return {'zip':str(output),'sha256':checksum,'entrega_id':receipt['entrega_id'],
                'estado':'ZIP_FORMATIVO_PROVISIONAL; ENTREGA_GITHUB_PENDIENTE',
                'verificacion_academica':PENDIENTE,'privacidad':'ENTREGA_RESTRINGIDA'}


def verificar_paquete(root: Path, source: Path | bytes) -> dict:
    files=leer_zip(source)
    receipt=json.loads(files.get('RECIBO_INDIVIDUAL.json',b'{}'))
    config=_config(root)
    legacy=receipt.get('schema')=='gem-individual/1'
    pilot=receipt.get('schema')==INDIVIDUAL_SCHEMA
    if (not (legacy or pilot) or receipt.get('grupo')!=config['grupo']
            or receipt.get('operacion')!=config['operacion']
            or receipt.get('estado_academico')!=('COMPLETO' if legacy else 'PENDIENTE_REVISION_DOCENTE')):
        raise ValueError('ZIP académico de otro grupo o esquema incompleto')
    uuid.UUID(receipt['entrega_id'])
    expected={n:sha_bytes(v) for n,v in files.items() if n!='RECIBO_INDIVIDUAL.json'}
    if receipt.get('sha256')!=expected: raise ValueError('Manifiesto SHA256 académico alterado/incompleto')
    lab=json.loads(files['progreso.json']); state=json.loads(files[FILE])
    projection=proyectar(state,PASOS,integridad='INTEGRA')
    if pilot:
        if (receipt.get('modo')!=MODO or receipt.get('dimensiones')!=projection['dimensiones']
                or json.loads(files.get('ESTADO_ACADEMICO.json',b'{}'))!=projection):
            raise ValueError('Estados del piloto o revisión docente no coinciden con el recorrido')
    revision=state.get('revision')
    if type(revision) is not int or not 1<=revision<=min(1500,len(files)):
        raise ValueError('Cantidad de revisiones inválida o excesiva')
    required={'RECIBO_INDIVIDUAL.json','progreso.json',FILE,'INFORME_ACADEMICO.md',
              'GEM_CONTINUIDAD_ACADEMICA.xlsx','FUENTES_VERSIONADAS.json',
              'fuentes/ACTIVIDADES_GEM.json','fuentes/CM03_HECHO_HISTORICO.md',lab.get('excel')}
    if pilot: required.add('ESTADO_ACADEMICO.json')
    required|={f'revisiones_gem/{n:06d}.json' for n in range(1,state.get('revision',0)+1)}
    if not required.issubset(files) or set(files)-required-{'decision_lab01_criterios.json'}:
        raise ValueError('ZIP académico incompleto o con archivos inesperados')
    if receipt['alias']!=lab.get('alias') or state.get('alias')!=lab.get('alias'):
        raise ValueError('Alias no corresponde al paquete')
    for key in ('grupo','operacion'):
        if lab.get(key)!=config[key] or state.get(key)!=config[key]: raise ValueError('Identidad cruzada')
    validar_cadena(state,files)
    if json.loads(files['fuentes/ACTIVIDADES_GEM.json'])!=catalogo(root):
        raise ValueError('Catálogo de evaluación divergente')
    if files['fuentes/CM03_HECHO_HISTORICO.md'].replace(b'\r\n',b'\n')!=(root/'docs/CM03_HECHO_HISTORICO.md').read_bytes().replace(b'\r\n',b'\n'):
        raise ValueError('Documento histórico CM03 divergente')
    # Cotas de seguridad ANTES de expandir los XLSX anidados.
    for name in (lab['excel'],'GEM_CONTINUIDAD_ACADEMICA.xlsx'):
        leer_zip(files[name])
    from openpyxl import load_workbook
    actual=load_workbook(BytesIO(files['GEM_CONTINUIDAD_ACADEMICA.xlsx']),read_only=True,data_only=False)
    expected_excel=load_workbook(BytesIO(excel_continuidad(root,state,piloto=pilot)),read_only=True,data_only=False)
    if actual.sheetnames!=expected_excel.sheetnames: raise ValueError('Hojas del Excel de continuidad divergentes')
    for sheet in actual.sheetnames:
        actual_rows=list(actual[sheet].values); expected_rows=list(expected_excel[sheet].values)
        if actual_rows!=expected_rows or any(c.data_type=='f' for row in actual[sheet] for c in row):
            raise ValueError('Excel de continuidad no corresponde a las respuestas registradas')
    actual.close(); expected_excel.close()
    if files['INFORME_ACADEMICO.md']!=informe(root,lab,state,piloto=pilot):
        raise ValueError('El informe legible no corresponde a las respuestas registradas')
    unique={}
    for item in state['actividades'].values():
        for event in item['intentos']:
            for e in event['evidencias']:
                unique[(e['ruta'],e['sha256'])]={'ruta':e['ruta'],'sha256':e['sha256'],'algoritmo':e['algoritmo']}
    if json.loads(files['FUENTES_VERSIONADAS.json'])!=list(unique.values()):
        raise ValueError('Índice de fuentes no corresponde al recorrido')
    # Valida Excel real, CM03 y coherencia documental en staging aislado.
    with TemporaryDirectory(prefix='gem_verificar_') as temp:
        staged=Path(temp)
        if lab.get('excel') not in files: raise ValueError('Falta Excel original')
        # El nombre lo vuelve a comprobar _validate_student; no extraer rutas arbitrarias.
        book=ruta_local(staged,lab['excel']); book.parent.mkdir(parents=True,exist_ok=True)
        book.write_bytes(files[lab['excel']]); (staged/'progreso.json').write_bytes(files['progreso.json'])
        comprobar_completo(root,staged,lab,state)
    return {'recibo':receipt,'archivos':files,'recorrido':state,'progreso':lab,
            'proyeccion':projection}
