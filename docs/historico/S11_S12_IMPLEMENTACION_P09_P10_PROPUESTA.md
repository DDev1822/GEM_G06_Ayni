# S11 + S12: P09 y P10 · release candidata v0.1

**Estado:** IMPLEMENTACIÓN DOCENTE EN REVISIÓN. **NO** es D08/D09 oficial ni se ha firmado el gate DD.

Se generan seis D09 espaciales sintéticos de **9,408 bloques cada uno**, con distinta morfología, semillas y dominios (**no** se replica Inti con un mero factor de ley). El modelo fundacional Inti Copper 3D v0.1 se preserva congelado; su D09 oficial sigue bloqueado por observaciones de techo/piso.

## Cadena de evidencia

- D00–D03: fuente existente por grupo. Se reutiliza D01 **solo para estadísticas de mineral procesado**, NO para reconstruir geología. Las fuentes XLSX originales no se publican en esta ruta y sus SHA-256 se registran en el manifiesto.
- D08: **propuesta docente** de parámetros comerciales y costos incrementales para trabajar P09. El precio de ejercicio 6,000 US$/t Cu **no es una cotización**. No se infiere costo marginal a partir del OPEX S04.
- D09: CSV sintético, coordenadas locales, 28 × 24 × 14 celdas de 25 × 25 × 10 m, densidades/leyes/recuperaciones proxy por dominio. MIX siempre queda como **mezcla operacional**, no unidad geológica. G05 tiene solo SUL-W + encajonante: no se inventa una segunda categoría a partir de MIX.
- Encajonante sin recuperación: marcado **no evaluable**, nunca enviado automáticamente a waste.
- Regla S12: destinos condicionales para *minado opcional* y para *material ya minado* sin duplicar minado hundido; no incluyen precedencias, topografía, pit, capacidad ni vida mina. **Suma de valores condicionales != VAN mina**.

## Archivos de implementación

- `src/gem_blocks/cohort_s11_s12.py` — lector D01 (`artifact_tool`), generador, validador, motor económico por decisión y exportador.
- `config/bloques/s11_s12/Gxx_D08_PARAMETROS_PROPUESTA.json` — seis supuestos diferenciados, todos sin ratificar.
- `datos/sinteticos/S12/Gxx/Gxx_D09_MODELO_SINTETICO_PROPUESTA.csv.gz` — seis CSV completos comprimidos, descargables en privado.
- `referencias/s11s12/GEM_S11_S12_6_CASOS_MANIFIESTO.json` — SHA-256 de las fuentes originales y salidas, resumen cuantitativo y limitaciones.
- `tests/test_s11_s12_release.py` — verificaciones de seis modelos, costos, integridad y ausencia de clasificación geológica ilegal.

## Cómo reproducir

Con Python ≥ 3.11, `numpy`, `scipy` y `artifact_tool`, los seis D01 oficiales extraídos del ZIP S04 bajo `fuentes_s04/G01/...G06/...`, ejecutar:

`PYTHONPATH=src python -m gem_blocks.cohort_s11_s12 fuentes_s04 salida_s11s12`

El programa lee el D01 verificable, escribe D08/D09 y solucionarios en la salida docente local. No sobrescribe los CSV congelados de Inti. El paquete visualizador/PDF/Excel se distribuye por separado desde los artefactos de la conversación, tras aprobación docente.

**Semana 11:** criterio económico y cutoff como función de decisión. **Semana 12:** valor por bloque, destino condicional, masa/ley ponderada/metal/valor por destino. **Semana 13:** restricciones T3, todavía no implementadas en este release.


## Validación GitHub Actions de la release candidata

La corrida remota [GEM S04–S12 #42368137210](https://github.com/DDev1822/Gestion_Empresas_Mineras_Repo/actions/runs/42368137210) finalizó **SUCCESS** el 7 de noviembre de 2026 (UTC). Se descubrieron 62 pruebas: **44 OK y 18 omitidas** por ausencia de fuentes S04/D01 privadas. Los cuatro tests de S11–S12 versionados y los tests de modelo maestro Inti pasan. El reporte no sustituye las **11 pruebas locales de desarrollo con seis D01 oficiales**, la validación Playwright de seis visores ni la revisión docente. Se corrigieron dos defectos de infraestructura en la suite heredada: ubicación de configuración `config/bloques/inti_master_v01.json` y pérdida de salto de línea al final del archivo, que alteraba su hash SHA-256. La restauración del salto de línea recupera el archivo original exacto; los datos económicos ni la geometría fueron modificados.
