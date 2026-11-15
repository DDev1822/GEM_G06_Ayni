"""CM04A y estructura mínima del microdiagnóstico; juicio pedagógico declarado."""
from pathlib import Path
import json
import re
import unicodedata

from gem_integridad import texto, sha_bytes, json_bytes


def validar_decision(values: dict, fields: dict, evidence: Path | None):
    missing=[name for name,cell in fields.items() if not values.get(cell)]
    if evidence is None:
        if missing:
            raise ValueError('Falta sustento de decisión. Una respuesta integrada puede cerrar con --evidencia-cierre y extractos reales; faltan: '+', '.join(missing))
        return None  # Compatibilidad histórica; no se reevalúa retrospectivamente.
    data=json.loads(Path(evidence).read_text(encoding='utf-8'))
    if data.get('evaluador') not in ('kai','docente'): raise ValueError('Identificar evaluador formativo')
    texto(data.get('razon'),'justificación formativa')
    quotes=data.get('criterios',{})
    if set(quotes)!=set(fields): raise ValueError('La decisión integrada debe cubrir los ocho criterios sustantivos')
    for name,quote in quotes.items():
        quote=texto(quote,name,limit=1800)
        if len(quote.split())<4 or not any(quote in v for v in values.values() if v):
            raise ValueError(f'{name}: cita un extracto literal sustantivo de la respuesta real')
    if not values.get(fields['recomendacion']): raise ValueError('Falta decisión real en C26')
    if quotes['dato1']==quotes['dato2'] or any(not re.search(r'\d',quotes[k]) for k in ('dato1','dato2')):
        raise ValueError('Sustentar dos datos distintos; no repetir la misma cita')
    return dict(data,tipo='JUICIO_FORMATIVO_DECLARADO; NO_NOTA',
                fuentes_sha256=sha_bytes(json_bytes(values)))


def validar_microdiagnostico(value: str):
    value=texto(value,'microdiagnóstico de restricción',limit=1200)
    normalized=''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
    required=(r'capacidad|capacidades|disponibilidad|utilizacion',r'brecha|meta|diferencia|acumulacion',
              r'falt|pendiente|medir|medicion|no demuestra|no permite')
    if len(normalized.split())<12 or any(not re.search(pattern,normalized) for pattern in required):
        raise ValueError('La restricción requiere microdiagnóstico propio: capacidades, brechas y evidencia faltante; POR DETERMINAR aislado no demuestra comprensión')
