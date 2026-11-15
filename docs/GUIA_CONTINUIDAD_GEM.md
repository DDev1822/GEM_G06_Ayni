# Continuidad GEM — piloto G06 / Ayni Copper

**Candidata local del 14/11/2026.** Esta guía describe la ruta nueva y sus controles. La presencia de código o de esta guía no acredita aceptación conversacional, publicación remota ni aprobación académica. D08/D09 conservan su estado de propuestas docentes sintéticas no oficiales.

**Actualización REL-A01 · PILOTO_DOCENTE_SUPERVISADO:** `comprendido` en el recorrido v1 registra únicamente cierre formativo declarado y permite continuar aprendiendo. La verificación académica independiente permanece `PENDIENTE_DOCENTE`, y una observación escrita conserva `EVIDENCIA_VISUAL_NO_VERIFICADA`. Los nuevos ZIP individuales usan `gem-individual/2` con `ESTADO_ACADEMICO.json` y cinco dimensiones separadas; los históricos `gem-individual/1` se leen como declaraciones heredadas. El recibo de publicación comprueba bytes remotos, no comprensión ni calificación. El grupo conserva estas distinciones en `gem-grupal-entrega/2`.

## Recorrido y compatibilidad

La ruta obligatoria es Laboratorio 01 → P09.1–P09.6 → P10.1–P10.6 → `DECISION_FINAL` → ZIP académico → depósito remoto verificado → despedida → Kai Integración Grupal. La primera decisión de Lab01 es un antecedente; se conserva y después se construye una decisión integradora nueva.

`progreso.json` versión 2, el Excel individual y sus fechas de sesión se preservan. Su estado `terminado` indica fin de Lab01, **no** fin del recorrido GEM. La continuidad nueva se guarda en un registro lateral versionado con sus revisiones, sin fabricar respuestas ni completar actividades antiguas. El estado global lo devuelve la API de continuidad. Si una ficha antigua está incompleta o es incoherente, conserva su contenido y resuelve el pendiente demostrado; no reinicies ni migres silenciosamente.

Las filas 13 y 14 continúan como `NO APLICADO AL CASO HISTÓRICO`, sin atribuir comprensión. P09 se realiza después como desarrollo didáctico obligatorio. Ningún resultado de S11 se atribuye retroactivamente a la clasificación original mineral/desmonte.

La exportación histórica `EXPORTAR_MI_TRABAJO.cmd` sigue sirviendo como respaldo parcial del laboratorio. No constituye el ZIP final GEM ni confirma entrega en GitHub.

## Uso interno de Kai

El estudiante observa, interpreta y decide; Kai ejecuta los registros con las herramientas disponibles. No se le exige abrir JSON, copiar comandos, aportar hashes ni editar Excel para avanzar conceptualmente.

1. Lee `grupo.json` y confirma que el paquete es G06 / Ayni Copper. Reanuda el alias existente; inicia Lab01 únicamente si no existe ficha y el alumno no ha pedido «no guardar».
2. Para recuperar el recorrido completo, ejecuta internamente:

   `python scripts/lab01/continuidad_gem.py --raiz <raiz_grupo> reanudar --alias <alias>`

3. Lee la actividad pendiente, los intentos reales, la dificultad y la próxima pregunta. Consulta la rúbrica de esa actividad en `docs/ACTIVIDADES_GEM.json`. No preguntes al alumno qué quiere hacer si la ruta ya lo determina.
4. Explica brevemente el concepto, indica el panel concreto del visor y plantea una sola pregunta. Termina la intervención y espera un nuevo mensaje real del estudiante. Una ejecución de herramienta o continuación del IDE no es un nuevo turno del alumno.
5. Después de cada respuesta real de P09/P10/final, registra un evento. Conserva también una respuesta incorrecta con `requiere_refuerzo`; su persistencia no la convierte en un resultado válido ni en comprensión.
6. Comprueba la salida del comando y relee el estado antes de afirmar que se guardó. Un fallo técnico no borra lo ya aprendido ni justifica inventar evidencia. Conserva en contexto la respuesta pendiente y reintenta cuando sea posible; no avances documentalmente mientras el registro exigido no exista.

Si el estudiante pide «no guardar», no crees ni actualices fichas, eventos o paquetes. Puedes continuar enseñando en el chat; no declares cumplida una entrega que no se produjo. No borres registros anteriores sin instrucción.

## Evento académico: palabras del alumno y evaluación declarada

El comando interno es:

`python scripts/lab01/continuidad_gem.py --raiz <raiz_grupo> registrar --alias <alias> --entrada <json_temporal_privado>`

El archivo de entrada contiene:

```json
{
  "actividad": "P09.1",
  "turno_id": "identificador-unico-del-turno-real",
  "pregunta": "Pregunta que Kai formuló realmente",
  "respuesta": "Palabras efectivamente emitidas por el estudiante",
  "interpretacion": "Interpretación técnica y económica expresada por el estudiante",
  "conclusion": "Hipótesis o conclusión que el estudiante construyó",
  "dificultad": "Dificultad pendiente identificada; vacío si se resolvió",
  "proxima_pregunta": "Pregunta concreta de comprobación que sigue pendiente en este paso",
  "estado": "en_curso",
  "evidencias": [
    {
      "ruta": "visor/G06_S11_S12_VISOR_INTERACTIVO.html",
      "panel": "fig-cutoff",
      "observacion": "Vista o resultado realmente consultado; indicar si solo se propuso el escenario",
      "escenario": {"precio": 6000, "rec": 1, "cp": 1}
    }
  ],
  "evaluacion": {
    "criterios": {},
    "razon": "Juicio formativo del tutor sobre lo demostrado y lo pendiente",
    "evaluador": "kai"
  },
  "confirmado": false
}
```

El ejemplo define el formato; **no** se registra como respuesta de un alumno. `turno_id` identifica un mensaje real y se conserva al reintentar su registro. No crees otro turno para simular que el alumno respondió dos veces.

Los estados son `en_curso`, `requiere_refuerzo` y `comprendido`. Cuando el paso no está comprendido, `proxima_pregunta` es obligatoria: conserva la pregunta concreta de aplicación o refuerzo que sigue pendiente, para reanudar sin inventar una respuesta ni reiniciar la lección. Una explicación del tutor, un asentimiento, una cifra aislada o una definición repetida no demuestran aplicación. Para cerrar un paso se necesitan al menos dos turnos distintos del estudiante, una aplicación o comprobación diferente, la interpretación del visual pertinente, todos sus criterios respaldados, ausencia de dificultad pendiente y evaluación confirmada.

En `evaluacion.criterios` usa las claves exactas del catálogo y, como valor, un extracto literal de una respuesta real del paso actual —la presente o una anterior del mismo paso— que sustente el criterio. No uses extractos de otra actividad, paráfrasis presentadas como citas ni texto redactado por Kai. En `razon` identifica por qué la aplicación es suficiente; no te limites a afirmar «cumple». `evaluador` permite `kai` o `docente`, identificando quién realiza el juicio formativo. El motor controla secuencia, presencia, fuentes, integridad y trazabilidad; **no sustituye la evaluación semántica ni califica**.

No se reconstruye una conversación completa. Se preserva la pregunta académica efectivamente hecha, la respuesta y los elementos necesarios para revisar ese aprendizaje. No registres saludos, confidencias, datos personales o comentarios ajenos a la actividad.

## S11: observación y sensibilidad

P09.1–P09.6 se apoyan en `S11 · Ley de corte`, `fig-cutoff` y `Fórmula y contraste`. D08 usa **6.000 US$/t Cu**, pagabilidad **96 %** y costos incrementales propuestos por dominio. Consulta los supuestos T2 reales de este grupo en `datos/G06_RESULTADOS_HISTORICOS.json` y en el visor; T2 y D08 son fuentes y ejercicios distintos.

P09.4 requiere tres ciclos completos, en turnos sucesivos y con una sola pregunta principal cada vez:

| Variable | Base de los otros controles | Qué se interpreta |
|---|---|---|
| `precio` | `rec=1`, `cp=1` | Cambio de ambos umbrales al modificar el precio desde 6000. |
| `rec` | `precio=6000`, `cp=1` | Cambio al modificar la recuperación proxy; no cambia el precio ni la ley contenida. |
| `cp` | `precio=6000`, `rec=1` | Cambio al modificar el costo de procesamiento y su consecuencia para la decisión. |

Antes de cambiar un control, pide una predicción y registra la respuesta con el escenario **propuesto**. Después de observar el gráfico cambiado, pide interpretación y registra la nueva respuesta con el escenario observado. Ambos eventos usan los mismos valores del escenario de contraste, la misma `variable` y momentos distintos:

```json
{"precio": 7500, "rec": 1, "cp": 1, "variable": "precio", "momento": "prediccion"}
```

```json
{"precio": 7500, "rec": 1, "cp": 1, "variable": "precio", "momento": "observacion"}
```

En el evento de predicción, `observacion` indica explícitamente que aún no se ha observado ese escenario; no atribuyas al alumno una lectura futura. La observación posterior pertenece a un turno diferente y registra lo que pudo ver realmente. Restablece las otras variables a base para cada ciclo. Los valores deben corresponder a los controles permitidos: precio 3500–8500 US$/t Cu en pasos de 100; `rec` 0,75–1,15 en pasos de 0,025; `cp` 0,65–1,45 en pasos de 0,05.

Cada criterio del catálogo de P09.4 requiere predicción previa, contraste posterior e interpretación gerencial de esa variable. No cierres el paso después de estudiar una sola sensibilidad. Una predicción errónea puede ser un buen punto de partida: guarda el error, explica la diferencia y espera la rectificación razonada.

Los controles S11 **solo actualizan los umbrales del gráfico S11**. No modifican las tablas por bloque ni los agregados S12. No declares que se recalculó S12 por moverlos.

## S12: modelo y límites

P10.1 utiliza `Panorama 3D` / `fig-3d`. El modelo sintético G06 contiene 9.408 bloques, en malla 28×24×14 y celdas 25×25×10 m. Si el navegador presenta proyección 2D, registra esa limitación; no afirmes que se rotó un 3D.

P10.2–P10.3 usan el identificador de un bloque G06 realmente consultado, `block-detail` y el escenario **base D08**. Guarda, por ejemplo, `escenario={"bloque_id":"G06_003000","precio":6000,"base_s12":true}`, sustituyendo el identificador por el bloque efectivamente observado. El motor comprueba que pertenezca al modelo de este grupo. Conecta toneladas de roca, ley, Cu contenido, Cu recuperable, Cu pagable e ingreso, sin confundir magnitudes. Compara los dos estados de extracción y sus costos relevantes.

P10.4 requiere tanto `fig-bank` como `fig-tonnage`; adjunta ambas referencias como evidencias internas. En la referencia a `fig-bank`, guarda el banco realmente consultado como entero entre 0 y 13, por ejemplo `escenario={"banco":7,"precio":6000,"base_s12":true}`. El banco es un subconjunto espacial. La curva tonelaje–ley es descriptiva y utiliza la envolvente mineralizada, **excluyendo encajonante**. No equivale a reservas ni a una política económica de corte.

P10.5 usa `aggregate-summary` y registra `escenario={"precio":6000,"base_s12":true}`: cada tabla cubre separadamente el universo de 9.408 bloques. No se suman las dos situaciones de extracción. El encajonante sin recuperación conserva su tonelaje y se mantiene sin evaluación económica: desconocido no es cero ni botadero. Los agregados son resultados precomputados del escenario base, no VAN de un proyecto.

P10.6 retoma un bloque real en `block-detail`, con `bloque_id`, `precio=6000` y `base_s12=true`, y exige explicar una restricción concreta que pueda invalidar la decisión: accesibilidad, precedencias, capacidad, espacio de stockpile u otra realmente pertinente. No declarar recursos, reservas, pit óptimo, calendario factible o VAN por haber obtenido valores de bloques positivos. S13 aborda restricciones todavía no resueltas en este ejercicio.

## Dos decisiones y cierre CM-04A

La primera decisión Lab01 se registra con R12 y permanece como antecedente. Puede ser una respuesta integrada, sin ocho subpreguntas artificiales. Los ocho criterios siguen siendo `alternativas`, `dato1`, `dato2`, `costos`, `van_tir`, `riesgo`, `recomendacion` y `condicion`.

Cuando una narrativa real en las celdas de decisión —por ejemplo `recomendacion`, C26— ya cubre esos ocho criterios, usa el parámetro interno `--evidencia-cierre <json>` al cierre de R12. El JSON contiene `criterios` con las ocho claves y extractos literales de las respuestas **ya escritas**, además de `evaluador` y `razon`. No rellenes celdas vacías con duplicados ni redactes argumentos por el estudiante. Si falta sustento, enseña y pregunta únicamente por el razonamiento que falta.

Después de P10.6 se construye `DECISION_FINAL`, vinculando diagnóstico Lab01, alternativas y economía T2/R11, aprendizajes S11/S12, riesgo y condición de revisión. Guarda esta decisión en la continuidad nueva, sin reemplazar la primera decisión. El estudiante debe defender su recomendación; Kai no elige en su nombre.

## ZIP y depósito seguro en el repositorio público

El exportador final interno es:

`python scripts/lab01/continuidad_gem.py --raiz <raiz_grupo> exportar --alias <alias> --salida <zip_academico_nuevo>`

El ZIP académico contiene el XLSX individual, `progreso.json`, continuidad y revisiones, informe legible, fuentes y manifiesto con recibo. Se conserva en almacenamiento restringido. No lo subas legible a GitHub: las respuestas por alias pueden identificar a una persona y siguen siendo evidencia académica privada. La ausencia de DNI o correo no basta para autorizar su difusión pública.

`publicacion_gem.py preparar --paquete <zip_academico> --salida <sobre_zip_nuevo> --clave-salida <archivo_fuera_del_repo>` crea un sobre cifrado autenticado para el repositorio público. El sobre contiene metadatos mínimos de grupo e identificador aleatorio y el ZIP académico cifrado; no alias ni respuestas legibles. La clave permanece fuera del repositorio y se transmite solo por un canal docente restringido. Cifrado e integridad no acreditan por sí solos autoría, consentimiento ni nota.

Antes de cualquier envío deben constar una política de entrega autorizada y un operador con permisos propios. No compartas credenciales ni presupongas que el estudiante puede hacer push. El representante o docente puede reunir varios sobres e incorporarlos por lote autorizado, conservando entregas previas y evitando commits por estudiante. La incorporación de evidencia y la publicación de software son acciones distintas.

El envío exige `publicacion_gem.py publicar --sobres <sobres> --claves <claves_en_el_mismo_orden> --confirmar-operador --autorizar-envio --politica-id <referencia_autorizada>`. Se proporciona una clave por sobre, todas fuera de la raíz del repositorio y bajo custodia del operador autorizado. Antes de cualquier envío se autentica el cifrado y se verifica el ZIP académico descifrado: el nombre `CONTENIDO_CIFRADO.bin` por sí solo no demuestra que esté cifrado. Nunca agregues las claves al lote público.

Los indicadores de confirmación y autorización no se agregan por iniciativa del tutor: corresponden a una instrucción expresa del operador autorizado para ese lote y su política. No inventes una referencia institucional ni consideres publicada una entrega porque se creó un archivo local.

Después se verifica con `publicacion_gem.py verificar --sobre <sobre_zip> --recibo <recibo>`. La comprobación debe descargar los bytes desde el repositorio original G06, contrastar SHA-256, ruta y commit y conservar el recibo. Hash o commit local, simulación de transporte y permiso de la cuenta docente no equivalen a entrega remota del estudiante. Si la confirmación falla, mantén `ENTREGA_PENDIENTE` y conserva el trabajo.

## Despedida y relevo

Solo después de completar los doce pasos, la decisión final, el ZIP íntegro y la verificación remota puede ejecutarse:

`python scripts/lab01/continuidad_gem.py --raiz <raiz_grupo> despedir --alias <alias> --sobre <sobre_zip> --recibo <recibo>`

Lee la salida antes de despedirte. Si existe recibo remoto válido, un mensaje posible es: «Has completado las actividades de preparación. El sobre de esta versión tiene un recibo de publicación verificado. Tu equipo puede continuar la integración. La comprensión académica y la nota siguen pendientes de revisión docente; puedes usar este recorrido para prepararte para el examen». Si falta recibo, reconoce el cierre formativo y explica que la entrega documental sigue pendiente.

Si la entrega sigue pendiente, explica ese estado sin declarar cerrado el recorrido documental. No certifiques aprobación ni fabriques recibos.

Kai Integración Grupal es una fase diferente: identifica integrantes y paquetes, recibe por canal restringido las claves, verifica grupo e integridad, compara interpretaciones y acompaña la deliberación. Recupera las seis preguntas oficiales, registra consensos realmente acordados, integra S11/S12 y prepara el Excel, manuscritos, evidencias y ZIP final docente. No presupone consenso, no redacta respuestas en nombre del equipo y no califica.

## Fuentes y aceptación

El catálogo vigente es `docs/ACTIVIDADES_GEM.json`. Las fuentes históricas recuperadas se conservan sin reescribir en `docs/historico/`: contrato S11/S12, enfoque académico, propuesta de implementación y memoria local. Sus descripciones antiguas no sustituyen la decisión actual de DD sobre el recorrido obligatorio.

La candidata exige pruebas automatizadas de continuidad, errores, integridad y regresión, más observación conversacional real en PyCharm/Copilot. Un test sintético, un prompt o una batería verde no sustituyen la aceptación pedagógica docente. No publicar código ni distribuir a alumnos reales sin la autorización docente posterior prevista para esta candidata.
