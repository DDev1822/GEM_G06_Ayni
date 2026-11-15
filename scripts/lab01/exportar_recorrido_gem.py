"""Entrada sencilla de exportación final; conserva el exportador parcial Lab01."""
from pathlib import Path
import json
from uuid import uuid4

from continuidad_gem import reanudar
from entrega_gem import exportar
from publicacion_gem import preparar


def main():
    root=Path(__file__).resolve().parents[2]
    alias=input('Tu alias de este grupo (sin nombre, DNI ni correo): ').strip()
    status=reanudar(root,alias)
    if status['etapa_actual'] not in ('ENTREGA_INDIVIDUAL','AGENTE_GRUPAL'):
        print('Aún falta '+status['etapa_actual']+'. Continúa con Kai; tu avance está conservado.')
        return 2
    token=uuid4().hex; private=root/'trabajos'/alias/'2026-11-11'/'entregas_gem'
    academic=private/f'ACADEMICO_{token}.zip'
    result=exportar(root,alias,academic)
    envelope=root.parent/f'SOBRE_GEM_{status["grupo"]}_{token}.zip'
    key=root.parent/'CLAVES_GEM_RESTRINGIDAS'/f'{token}.gem-key.json'
    public=preparar(root,academic,envelope,key)
    print('ZIP formativo provisional para revisión docente: '+str(academic))
    print('Sobre cifrado para el operador autorizado: '+str(envelope))
    print('Clave de revisión restringida: '+str(key))
    print('Entrega la clave al docente por el canal restringido. No la subas a GitHub.')
    print('El sobre está preparado. La entrega sigue pendiente hasta confirmar sus bytes en GitHub.')
    print('La verificación académica y la calificación docente siguen pendientes; este ZIP no certifica comprensión.')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,ImportError) as exc:
        print('No se completó la exportación GEM: '+str(exc)); raise SystemExit(2)
