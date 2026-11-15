"""Primitivas locales GEM: integridad, escritura sin sobrescritura y ZIP acotados."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


REPOS = {
    'G01': 'DDev1822/GEM_G01_Qhapaq', 'G02': 'DDev1822/GEM_G02_Kallpa',
    'G03': 'DDev1822/GEM_G03_Sumaq', 'G04': 'DDev1822/GEM_G04_Tikari',
    'G05': 'DDev1822/GEM_G05_Wayra', 'G06': 'DDev1822/GEM_G06_Ayni',
}


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def texto(value, label: str, *, limit=12000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value)>limit or '\x00' in value:
        raise ValueError(f'{label}: se requiere texto real no vacío (máximo {limit})')
    return value.strip()


def ruta_local(root: Path, relative: str) -> Path:
    if not isinstance(relative,str) or '\\' in relative or ':' in relative:
        raise ValueError('Ruta relativa inválida')
    p = PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(x in ('..','.') for x in p.parts):
        raise ValueError('Ruta fuera del paquete')
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Ruta o enlace fuera del paquete')
    return target


def nuevo(path: Path, data: bytes) -> None:
    """Instala un archivo completo de forma exclusiva, incluso ante dos escritores."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.gem-', delete=False) as tmp:
        temp = Path(tmp.name)
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
    try:
        try:
            os.link(temp, path)  # falla si ya existe; jamás reemplaza una entrega
        except PermissionError:
            if os.name != 'nt':
                raise
            # Windows puede impedir hardlinks en entornos restringidos. rename
            # es exclusivo en Windows: si el destino existe, falla sin reemplazo.
            os.rename(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def atomico(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.gem-head-',delete=False) as tmp:
        temp=Path(tmp.name)
        tmp.write(json_bytes(value)); tmp.flush(); os.fsync(tmp.fileno())
    try:
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def bloqueo(folder: Path):
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'.gem.lock'
    # Bloqueo del SO: se libera incluso al terminar proceso/IDE abruptamente.
    # El archivo estable NO se borra: eliminar un lock abierto crearía carreras.
    handle=path.open('a+b')
    handle.seek(0,2)
    if handle.tell()==0: handle.write(b'0'); handle.flush()
    handle.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError('Otra escritura GEM está activa; reintentar al finalizar') from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        handle.close()


def leer_zip(source: Path | bytes) -> dict[str,bytes]:
    raw = source.read_bytes() if isinstance(source,Path) else source
    if len(raw)>80_000_000:
        raise ValueError('ZIP excede 80 MB')
    with zipfile.ZipFile(BytesIO(raw)) as z:
        infos=z.infolist(); names=[i.filename for i in infos]
        if len(infos)>1500 or len(names)!=len(set(names)):
            raise ValueError('ZIP duplicado o excesivo')
        if sum(i.file_size for i in infos)>160_000_000:
            raise ValueError('ZIP expandido excesivo')
        result={}
        for i in infos:
            name=i.filename; p=PurePosixPath(name)
            if (not p.parts or p.is_absolute() or '\\' in name or ':' in name
                    or '..' in p.parts or name.startswith('.')
                    or stat.S_ISLNK(i.external_attr>>16) or i.is_dir()
                    or i.file_size>40_000_000 or i.file_size>max(i.compress_size,1)*1000):
                raise ValueError('Entrada ZIP insegura o excesiva')
            result[name]=z.read(i)  # comprueba CRC; no extrae rutas
        return result


def escribir_zip(output: Path, files: dict[str,bytes]) -> Path:
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for name,data in sorted(files.items()): z.writestr(name,data)
    raw=stream.getvalue()
    if leer_zip(raw)!=files: raise RuntimeError('ZIP no confirmado')
    nuevo(output,raw)
    return output
