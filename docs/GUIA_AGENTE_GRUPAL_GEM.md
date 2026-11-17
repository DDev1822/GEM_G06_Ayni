# Kai Integración GEM — guía operativa

Motor: `scripts/lab01/kai_grupal_gem.py`. Agente: `.github/agents/kai-grupal.agent.md`. Trabajo privado en `.gem_grupal/<UUID>/`; sin publicaciones automáticas, calificación ni consenso inventado.

El entorno requiere Python y `openpyxl` para producir el libro adicional S11/S12. La recepción y el estado usan la biblioteca estándar y los verificadores del paquete GEM. El Excel maestro y los paquetes individuales recibidos se preservan.

## Recorrido

1. Crear con padrón explícito de alias: `python scripts/lab01/kai_grupal_gem.py crear --padron alias1 alias2`. Conservar `expediente_id`.
2. Recibir cada entrega: `recibir --expediente UUID --sobre SOBRE.zip --clave CLAVE --recibo-publicacion RECIBO.json`. La clave permanece fuera del repositorio y nunca se incluye en la entrega. Se verifican grupo, operación, alias del padrón, UUID de entrega, completitud, manifiestos y la llegada al GitHub original del grupo. `--paquete ACADEMICO.zip` es recepción local con publicación pendiente.
3. `comparar --expediente UUID` recupera los textos de P09/P10/decisión final y los registros breves de las seis preguntas. La comparación no decide automáticamente si las interpretaciones son correctas o equivalentes. El XLSX individual incluido conserva las respuestas íntegras del Lab01.
4. `intervenir --expediente UUID --alias ALIAS --tema PREGUNTA_1 --turno-id ID_REAL --texto "RESPUESTA REAL" --tipo propuesta`. Solo registra una intervención efectivamente recibida. Devuelve `intervencion_id`.
5. Cada integrante confirma esa propuesta: `intervenir ... --tipo confirmacion --propuesta-id UUID_PROPUESTA --texto "CONFIRMACIÓN REAL"`. El contenido real queda visible al docente. El programa comprueba los registros, no autentica a la persona que escribió.
6. `acordar --expediente UUID --tema PREGUNTA_1 --propuesta-id UUID_PROPUESTA --confirmaciones UUID_CONFIRMACION_1 UUID_CONFIRMACION_2`. Exige una confirmación posterior de cada alias del padrón, sin duplicados. Una deliberación posterior requiere nueva ronda de confirmación. Los acuerdos anteriores se conservan.
7. Repetir para `PREGUNTA_1` a `PREGUNTA_6`, `S11`, `S12` y `DECISION_FINAL`. Las preguntas oficiales se leen del archivo del grupo, sin reconstruirlas. En la decisión final se agregan `--extractos EXTRACTOS.json` y, cuando exista evidencia económica, `--sustento SUSTENTO.json`. El primero contiene `diagnostico`, `costos`, `recomendacion` y `condicion`; cada valor debe aparecer literalmente en la propuesta acordada. No son preguntas adicionales. El sustento se describe abajo. Ambos archivos se preparan por Kai en `.gem_grupal/<UUID>/`, directorio privado excluido de Git; el estudiante aporta e interpreta la información, pero no tiene que escribir JSON manualmente.
8. `adjuntar --expediente UUID --tipo manuscrito --archivo DOCUMENTO --descripcion "EVIDENCIA REAL"`. Reunir también `retroalimentacion` y `evidencia_visor`. Manuscrito y evidencia de visor requieren PDF o imagen PNG/JPG/JPEG/WebP; la retroalimentación admite además TXT/Markdown UTF-8 y DOCX. Archivos regulares, hasta 35 MB. Se comprueba el tipo básico, integridad y presencia; la legibilidad y pertinencia requieren cotejo humano.
9. `preparar --expediente UUID` crea libros nuevos desde la plantilla grupal y los acuerdos. No reemplaza libros existentes. El padrón real se refleja en las nueve filas disponibles de la plantilla y queda completo en la hoja adicional `PADRON`, incluidos integrantes pendientes. El libro adicional contiene S11/S12, decisión y matriz de respuestas individuales con celdas de texto, sin ejecutar fórmulas recibidas como respuesta.
10. `estado --expediente UUID --verificar-red` comprueba pendientes y revalida las publicaciones. `exportar-docente --expediente UUID` genera el ZIP restringido, el recibo y su SHA-256 externo. `--salida` puede apuntar al expediente privado o a una carpeta fuera del repositorio.

Todos los comandos admiten `--raiz RUTA` **antes** del subcomando. La salida es JSON y los errores terminan con código 2. `--help` detalla las opciones.

## Sustento económico de DECISION_FINAL

Kai recupera las evidencias individuales, identifica con el equipo el problema y las alternativas y consulta solamente las fuentes de `grupo.json`: `datos/Gxx_RESULTADOS_HISTORICOS.json`, los archivos S04 y `visor/Gxx_S11_S12_VISOR_INTERACTIVO.html`. No copia cifras entre operaciones. S04 Base, T2/R11 y S11/S12 son rutas distintas; valor de bloque no es VAN. Un dato ausente se conserva pendiente y nunca se reemplaza por cero.

`SUSTENTO.json` es un objeto con esta estructura exacta:

```json
{
  "ruta": "S11_S12_BLOQUE",
  "problema": "Texto literal incluido en la propuesta",
  "alternativas": "Texto literal incluido en la propuesta",
  "comparacion": "Texto literal incluido en la propuesta",
  "restricciones": "Texto literal incluido en la propuesta",
  "recomendacion": "Texto literal incluido en la propuesta",
  "condicion": "Texto literal incluido en la propuesta",
  "kpi": [
    {
      "codigo": "CODIGO_DE_LA_FUENTE",
      "valor": "VALOR_DECLARADO",
      "unidad": "UNIDAD_DE_LA_FUENTE",
      "fuente": "RUTA_EXACTA_DE_LA_FUENTE",
      "escenario": "ESCENARIO_O_CONDICION",
      "periodo": "PERIODO_DE_LA_FUENTE",
      "interpretacion": "Interpretación literal incluida en la propuesta"
    },
    {
      "codigo": "SEGUNDO_CODIGO_DE_LA_MISMA_RUTA_COMPATIBLE",
      "valor": "SEGUNDO_VALOR_DECLARADO",
      "unidad": "UNIDAD_DE_LA_FUENTE",
      "fuente": "RUTA_EXACTA_DE_LA_FUENTE",
      "escenario": "ESCENARIO_O_CONDICION",
      "periodo": "PERIODO_DE_LA_FUENTE",
      "interpretacion": "Segunda interpretación literal incluida en la propuesta"
    }
  ],
  "bloque_id": "Gxx_IDENTIFICADOR_DE_BLOQUE",
  "estado_extraccion": "YA_EXTRAIDO"
}
```

Las claves son obligatorias y no se agregan otras. `ruta` admite:

- `S11_S12_BLOQUE`: usa un bloque de la operación y `estado_extraccion` igual a `YA_EXTRAIDO` o `MINADO_OPCIONAL`.
- `OPERACIONAL_T2_R11`: usa KPI homogéneos T2/R11 de una misma alternativa; `bloque_id` y `estado_extraccion` son `null`.
- `OPERACIONAL_S04`: conserva cifras Base S04 trazables, pero queda `PENDIENTE_SUSTENTO` mientras falte una comparación homogénea; ambos campos son `null`.

Cada texto de `problema`, `alternativas`, `comparacion`, `restricciones`, `recomendacion`, `condicion` e `interpretacion` debe aparecer literalmente en la propuesta registrada. El motor exige dos KPI distintos y coteja grupo, cifra, unidad, fuente, escenario y periodo. También liga la propuesta, el sustento y las fuentes a la revisión vigente mediante hashes.

Ejemplo de ejecución, sin cifras genéricas:

```text
python scripts/lab01/kai_grupal_gem.py --raiz RUTA acordar --expediente UUID --tema DECISION_FINAL --propuesta-id UUID_PROPUESTA --confirmaciones UUID_C1 UUID_C2 UUID_C3 --extractos .gem_grupal/UUID/EXTRACTOS.json --sustento .gem_grupal/UUID/SUSTENTO.json
```

Sin `--sustento`, la CLI conserva compatibilidad: la decisión puede registrarse, pero queda `INSUFICIENTE` si es genérica o `PENDIENTE_SUSTENTO` si su texto es desarrollado y carece de fuente estructurada. Un JSON malformado, un KPI ajeno, falso o incompatible termina con código 2 y no modifica el expediente. Si cambia la propuesta, el sustento o una fuente, `estado` devuelve `PENDIENTE_SUSTENTO`; se debe deliberar, confirmar y validar una nueva revisión.

Los estados de `CALIDAD_GERENCIAL` son `INSUFICIENTE`, `PENDIENTE_SUSTENTO` y `PREPARADA_PARA_REVISION_DOCENTE`. Ninguno equivale a aprobación, verificación académica o calificación. Después de `acordar`, ejecutar `estado --expediente UUID` y explicar al equipo el estado y los pendientes concretos.

## Qué demuestra cada estado

`LOCAL_SIN_PUBLICACION` permite iniciar discusión con una evidencia verificada localmente; no satisface la incorporación obligatoria al GitHub original. `PUBLICADO_GITHUB_VERIFICADO` solo procede del verificador que descarga el sobre en su commit y comprueba su pertenencia a la rama autorizada. No se simula una publicación al crear un archivo de recibo.

`COMPLETO` en la entrega grupal significa que no faltan integrantes del padrón, publicaciones verificadas, nueve acuerdos explícitos o las tres categorías de adjuntos. El ZIP contiene `evaluacion_docente=PENDIENTE`. Esa comprobación documental no certifica autoría, comprensión, legibilidad ni suficiencia de los argumentos.

Una recepción incompatible se rechaza sin reemplazar otra entrega. Si un integrante cambió sustancialmente su ZIP, el equipo revisa la discrepancia y crea otro expediente; las versiones anteriores permanecen. Una misma entrega idéntica se reconoce sin duplicar y puede incorporar después su prueba de publicación.

El expediente usa un bloqueo del sistema operativo, revisiones inmutables y un journal recuperable. El bloqueo se libera incluso si el proceso o IDE termina abruptamente; el archivo estable `.gem.lock` se conserva y no se borra. Si otra escritura sigue activa, esperar a que termine antes de reintentar. No reiniciar el expediente ni borrar evidencias para ocultar una discrepancia.

## Contenido del ZIP docente

Incluye el Excel grupal histórico, el libro adicional S11/S12, los ZIP académicos individuales, las pruebas de procedencia disponibles, los adjuntos, las seis preguntas fuente, el estado y las intervenciones/acuerdos reales, un informe legible y `RECIBO_GRUPAL.json` con SHA-256 de todos los demás archivos. No incluye claves de descifrado. Los ZIP incompletos conservan sus motivos de no completitud.

Este ZIP contiene evidencia académica privada. Su destino es el docente por canal restringido; el repositorio público solo admite los sobres cifrados preparados por el procedimiento individual autorizado. Preparar el ZIP docente no demuestra recepción por el profesor.
