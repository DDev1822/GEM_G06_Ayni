"""Depósito controlado de sobres cifrados; preparar nunca acredita publicación."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from entrega_gem import verificar_paquete
from gem_integridad import (REPOS, escribir_zip, json_bytes, leer_zip, nuevo,
                            sha_bytes, sha_file, texto)
from lab01_common_v2 import _config, _read_json


def identidad(root: Path) -> tuple[dict,str]:
    config=_config(root); repo=REPOS[config['grupo']]
    if config.get('repo_url','').rstrip('/').removesuffix('.git')!='https://github.com/'+repo:
        raise ValueError('grupo.json no apunta al repositorio original de este grupo')
    if config.get('rama_base')!='main': raise ValueError('La rama oficial del grupo debe ser main')
    return config,repo


def run(args: list[str], root: Path, *, binary=False):
    result=subprocess.run(args,cwd=root,capture_output=True,timeout=120)
    if result.returncode:
        # Nunca incluir stdout/stderr de un proceso autenticado ni sus credenciales.
        raise RuntimeError(f'{args[0]} falló (código {result.returncode}); no se acredita envío')
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


class GitHub:
    """Única frontera de red. Las pruebas usan un transporte explícitamente ficticio."""
    def __init__(self,root: Path,repo: str): self.root=root; self.repo=repo

    def api(self,endpoint):
        return json.loads(run(['gh','api',endpoint],self.root))

    def metadata(self): return self.api('repos/'+self.repo)

    def main_sha(self): return self.api('repos/'+self.repo+'/git/ref/heads/main')['object']['sha']

    def es_ancestro(self,commit,head):
        if commit==head: return True
        return self.api(f'repos/{self.repo}/compare/{commit}...{head}').get('status') in ('ahead','identical')

    def archivo(self,path,commit):
        return run(['gh','api',f'repos/{self.repo}/contents/{path}?ref={commit}',
                    '-H','Accept: application/vnd.github.raw+json'],self.root,binary=True)


def preparar(root: Path, paquete: Path, salida: Path, clave_salida: Path) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    config,repo=identidad(root); original=paquete.read_bytes(); verified=verificar_paquete(root,original)
    if salida.exists() or clave_salida.exists(): raise FileExistsError('Sobre o clave ya existe; no se sobrescribe')
    if clave_salida.resolve().is_relative_to(root.resolve()):
        raise ValueError('La clave debe quedar fuera del repositorio y entregarse por canal docente restringido')
    if salida.resolve()==clave_salida.resolve(): raise ValueError('Sobre y clave deben ser distintos')
    key=AESGCM.generate_key(bit_length=256); nonce=os.urandom(12)
    receipt=verified['recibo']
    meta={'schema':'gem-sobre-publico/1','grupo':config['grupo'],'repo':repo,
          'entrega_id':receipt['entrega_id'],'academico_sha256':sha_bytes(original),
          'cifrado':'AES-256-GCM','nonce_b64':base64.b64encode(nonce).decode('ascii')}
    ciphertext=AESGCM(key).encrypt(nonce,original,json_bytes(meta))
    secret={'schema':'gem-clave-restringida/1','grupo':config['grupo'],
            'entrega_id':receipt['entrega_id'],'clave_b64':base64.b64encode(key).decode('ascii')}
    nuevo(clave_salida,json_bytes(secret))
    try: os.chmod(clave_salida,0o600)
    except OSError: pass
    escribir_zip(salida,{'META_PUBLICA.json':json_bytes(meta),'CONTENIDO_CIFRADO.bin':ciphertext,
                        'LEEME_PUBLICO.txt':('Evidencia académica cifrada. Revisión solo mediante clave docente restringida.\n'
                                              'SHA-256 acredita integridad; no calificación ni identidad civil.\n').encode('utf-8')})
    abrir_sobre(root,salida,clave_salida)
    from continuidad_gem import contexto
    folder,_,_=contexto(root,receipt['alias'])
    local={'entrega_id':meta['entrega_id'],'sobre_sha256':sha_file(salida),
           'academico_sha256':meta['academico_sha256'],'autenticado':'AES256GCM_VERIFICADO'}
    nuevo(folder/'sobres_verificados_gem'/f"{meta['entrega_id']}-{sha_file(salida)}.json",json_bytes(local))
    return {'estado':'SOBRE_PREPARADO; NO_PUBLICADO','entrega_id':receipt['entrega_id'],
            'sobre':str(salida),'sobre_sha256':sha_file(salida),'clave':'CREADA_FUERA_DEL_REPOSITORIO; NO_COMPARTIR_EN_GITHUB'}


def metadatos_sobre(root: Path, source: Path) -> dict:
    config,repo=identidad(root); files=leer_zip(source)
    if set(files)!={'META_PUBLICA.json','CONTENIDO_CIFRADO.bin','LEEME_PUBLICO.txt'}:
        raise ValueError('El depósito público admite únicamente un sobre cifrado, sin archivos académicos legibles')
    meta=json.loads(files['META_PUBLICA.json'])
    if set(meta)!={'schema','grupo','repo','entrega_id','academico_sha256','cifrado','nonce_b64'}:
        raise ValueError('Metadatos públicos inesperados; posible dato privado')
    if (meta.get('schema')!='gem-sobre-publico/1' or meta.get('grupo')!=config['grupo']
            or meta.get('repo')!=repo or meta.get('cifrado')!='AES-256-GCM'):
        raise ValueError('Sobre de otro grupo/repo o cifrado incompatible')
    uuid.UUID(meta['entrega_id'])
    if not re.fullmatch('[a-f0-9]{64}',meta['academico_sha256']): raise ValueError('SHA académico inválido')
    if len(base64.b64decode(meta['nonce_b64'],validate=True))!=12: raise ValueError('Nonce inválido')
    # El texto público es fijo; no puede aprovecharse para filtrar un nombre o respuesta.
    expected=('Evidencia académica cifrada. Revisión solo mediante clave docente restringida.\n'
              'SHA-256 acredita integridad; no calificación ni identidad civil.\n').encode('utf-8')
    if files['LEEME_PUBLICO.txt']!=expected or len(files['CONTENIDO_CIFRADO.bin'])<16:
        raise ValueError('Contenido público no permitido')
    return meta


def abrir_sobre(root: Path, sobre: Path, clave: Path) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    meta=metadatos_sobre(root,sobre); secret=_read_json(clave)
    if secret.get('entrega_id')!=meta['entrega_id'] or secret.get('grupo')!=meta['grupo']:
        raise ValueError('Clave docente no corresponde al sobre')
    try:
        key=base64.b64decode(secret['clave_b64'],validate=True)
        raw=AESGCM(key).decrypt(base64.b64decode(meta['nonce_b64']),
                              leer_zip(sobre)['CONTENIDO_CIFRADO.bin'],json_bytes(meta))
    except (InvalidTag,ValueError,KeyError) as exc:
        raise ValueError('No se pudo autenticar/descifrar la evidencia') from exc
    if sha_bytes(raw)!=meta['academico_sha256']: raise ValueError('Integridad del ZIP académico no coincide')
    parsed=verificar_paquete(root,raw)
    if parsed['recibo']['entrega_id']!=meta['entrega_id']: raise ValueError('Identidad de entrega cifrada divergente')
    return raw


def ruta_sobre(meta: dict,checksum: str) -> str:
    return f"entregas/individuales/{meta['entrega_id']}/{checksum}.zip"


def _verificar(root: Path,sobre: Path,receipt: dict,client=None) -> dict:
    config,repo=identidad(root); meta=metadatos_sobre(root,sobre); checksum=sha_file(sobre)
    if (receipt.get('schema')!='gem-publicacion/1' or receipt.get('repo')!=repo
            or receipt.get('grupo')!=config['grupo'] or receipt.get('entrega_id')!=meta['entrega_id']
            or receipt.get('sobre_sha256')!=checksum or receipt.get('ruta')!=ruta_sobre(meta,checksum)
            or not re.fullmatch('[a-f0-9]{40}',receipt.get('commit',''))):
        raise ValueError('Recibo remoto no corresponde al sobre y repositorio originales')
    client=client or GitHub(root,repo)
    metadata=client.metadata()
    if metadata.get('full_name')!=repo or metadata.get('private') is not False:
        raise ValueError('Repositorio original público no confirmado')
    head=client.main_sha()
    if not client.es_ancestro(receipt['commit'],head): raise ValueError('El commit no está incorporado a main')
    remote=client.archivo(receipt['ruta'],receipt['commit'])
    current=client.archivo(receipt['ruta'],head)
    if sha_bytes(remote)!=checksum or remote!=sobre.read_bytes() or current!=remote:
        raise ValueError('Bytes remotos no corresponden al ZIP individual')
    return dict(receipt,estado='PUBLICADO_GITHUB_VERIFICADO',head_verificado=head,
                verificado_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))


def verificar_recibo(root: Path,sobre: Path,recibo: Path) -> dict:
    return _verificar(root,sobre,_read_json(recibo))


def publicar(root: Path,sobres: list[Path],confirmar: bool,autorizar: bool,politica_id: str,claves: list[Path] | None=None) -> dict:
    if not confirmar or not autorizar: raise PermissionError('Falta confirmación de operador y autorización de envío')
    politica_id=texto(politica_id,'identificador de política docente de entrega restringida',limit=200)
    config,repo=identidad(root)
    if not sobres: raise ValueError('No hay sobres para incorporar')
    if not claves or len(claves)!=len(sobres): raise ValueError('Cada sobre requiere clave restringida para autenticar el cifrado antes del envío')
    entries=[]; seen=set()
    for p,key in zip(sobres,claves):
        if key.resolve().is_relative_to(root.resolve()): raise ValueError('Las claves deben custodiarse fuera del repositorio')
        raw=p.read_bytes()
        abrir_sobre(root,raw,key)  # .bin por sí solo NO prueba confidencialidad
        meta=metadatos_sobre(root,raw); checksum=sha_bytes(raw)
        if meta['entrega_id'] in seen: raise ValueError('Una entrega aparece dos veces en el lote')
        seen.add(meta['entrega_id']); entries.append((p,meta,checksum,ruta_sobre(meta,checksum),raw))
    if run(['git','remote','get-url','origin'],root).rstrip('/').removesuffix('.git')!='https://github.com/'+repo:
        raise ValueError('origin del operador no coincide con el grupo original')
    client=GitHub(root,repo); info=client.metadata()
    if (info.get('full_name')!=repo or info.get('private') is not False
            or not info.get('permissions',{}).get('push')):
        raise PermissionError('La cuenta autenticada no confirmó permiso de escritura al repositorio público original')
    # Un clon fresco impide subir por accidente cambios de software o claves locales.
    stage=root/'.gem_publicacion'/str(uuid.uuid4()); stage.parent.mkdir(parents=True,exist_ok=True)
    run(['git','clone','--single-branch','--branch','main','https://github.com/'+repo+'.git',str(stage)],root)
    new=[]; existing=[]
    for source,meta,checksum,relative,raw in entries:
        dest=stage/relative
        if dest.exists():
            if sha_file(dest)!=checksum: raise ValueError('Entrega previa divergente; no se sobrescribe')
            previous=run(['git','log','-1','--format=%H','--',relative],stage)
            existing.append((source,meta,checksum,relative,previous)); continue
        if dest.parent.exists() and any(dest.parent.iterdir()):
            raise FileExistsError('Ya existe otra versión para este identificador de entrega')
        nuevo(dest,raw); new.append(relative)
    if new:
        run(['git','add','--',*new],stage)
        run(['git','commit','-m',f"GEM {config['grupo']}: depósito individual cifrado ({len(new)} entregas)"],stage)
        changed=run(['git','diff-tree','--no-commit-id','--name-only','-r','HEAD'],stage).splitlines()
        if sorted(changed)!=sorted(new): raise RuntimeError('El commit incluye algo ajeno a los sobres autorizados')
        commit=run(['git','rev-parse','HEAD'],stage)
        # Push normal: el servidor rechaza carreras y ningún historial se fuerza.
        run(['git','push','origin','HEAD:refs/heads/main'],stage)
    receipts=[]
    existing_commits={item[3]:item[4] for item in existing}
    for source,meta,checksum,relative,raw in entries:
        sha=existing_commits[relative] if relative in existing_commits else commit
        receipt={'schema':'gem-publicacion/1','grupo':config['grupo'],'repo':repo,
                 'entrega_id':meta['entrega_id'],'sobre_sha256':checksum,'ruta':relative,
                 'commit':sha,'politica_id':politica_id}
        verified=_verificar(root,stage/relative,receipt,client)
        path=root/'.gem_recibos'/f"{meta['entrega_id']}-{sha}.json"
        if not path.exists(): nuevo(path,json_bytes(verified))
        receipts.append({'recibo':str(path),**verified})
    return {'estado':'LOTE_PUBLICADO_Y_VERIFICADO','entregas':receipts,
            'nota':'Sin calificación ni aprobación docente; claves fuera de GitHub.'}


def main():
    p=argparse.ArgumentParser(description='GEM — entrega cifrada en repositorio original público')
    p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parents[2]); s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('preparar')
    for key in ('paquete','salida','clave-salida'): a.add_argument('--'+key,type=Path,required=True)
    a=s.add_parser('publicar'); a.add_argument('--sobres',type=Path,nargs='+',required=True)
    a.add_argument('--claves',type=Path,nargs='+',required=True)
    a.add_argument('--confirmar-operador',action='store_true'); a.add_argument('--autorizar-envio',action='store_true')
    a.add_argument('--politica-id',required=True)
    a=s.add_parser('verificar'); a.add_argument('--sobre',type=Path,required=True); a.add_argument('--recibo',type=Path,required=True)
    args=p.parse_args()
    try:
        root=args.raiz.resolve()
        if args.cmd=='preparar': out=preparar(root,args.paquete.resolve(),args.salida.resolve(),args.clave_salida.resolve())
        elif args.cmd=='publicar': out=publicar(root,args.sobres,args.confirmar_operador,args.autorizar_envio,args.politica_id,args.claves)
        else: out=verificar_recibo(root,args.sobre.resolve(),args.recibo.resolve())
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(f'PUBLICACION GEM: {exc}',file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
