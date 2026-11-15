# Kai Gestión — contrato de aprendizaje S11/P09 y S12/P10

**Estado:** propuesta operativa para revisión docente, 2026-11-08. **No autoriza** publicar D08/D09 como datos oficiales ni distribuir el repositorio docente. Fuentes rectoras: Guía Maestra del Proyecto Integral 2026-2; `docs/ENFOQUE_ACADEMICO.md`; `docs/S11_S12_IMPLEMENTACION_P09_P10_PROPUESTA.md`; modelos y configuraciones en Git.

## 1. Decisión de diseño: conocimientos, no manipulación de archivos

El desarrollo Python, las seis geometrías sintéticas, el motor de valorización y las visualizaciones **ya existen**. La tarea del estudiante NO es construirlos, instalarlos, buscar rutas, elegir CSV, editar JSON, escribir Python ni demostrar que el software corrió. Ese trabajo técnico corresponde al entorno docente, **antes** de la sesión. El estudiante vive una exploración guiada de una operación, como si participara en su desarrollo: anticipa consecuencias, observa tablas y gráficos, razona y recomienda una decisión.

**Conversación estándar, un paso por turno:** contexto minero breve → explicar el porqué de una decisión ya modelada y el parámetro del ejercicio → pedir **una** predicción o interpretación → mostrar o indicar una **visualización humana** preparada → contrastar respuesta → avanzar o dar una pista y reevaluar. La respuesta técnica puede profundizarse si el alumno pregunta, pero no se entrega una lista de rutas/comandos ni se lo envía a recopilar registros.

**La única barrera de aprendizaje es conceptual.** Una respuesta incompleta recibe una explicación más concreta, un ejemplo distinto y una nueva pregunta de verificación. El tutor **no** exige adjuntar pruebas, capturas, hashes, hojas o archivos para avanzar por la ruta conceptual. La aprobación técnica de los modelos y la evaluación académica formal del profesor son procesos independientes.

**Dos decisiones distintas:** el docente fija los modelos, reglas de cálculo y escenarios de aula; **el alumno decide gerencialmente** si recomendaría una intervención, qué riesgos reconoce y cuándo cambiaría su consejo. Kai no inventa datos, no presenta hipótesis como observaciones y no utiliza un único KPI como decisión final.

## 2. Principios de rigor no negociables

- Valor económico **antes de impuestos**. No introducir impuestos, financiamiento o cotizaciones actuales.
- D08 G01–G06: **hipótesis docentes editables no ratificadas**; precio del cobre US$ 6.000/t: ejemplo académico, no dato de mercado.
- D09 G01–G06: **seis geometrías sintéticas distintas**, 9.408 bloques por grupo; no son recursos/reservas. D01 procesado es un ancla descriptiva, no ley media in situ.
- No confundir **decisión de minar un bloque** con **destino de material ya extraído**: el costo de minado evitable se cuenta en la primera y es hundido en la segunda.
- No imponer un cutoff universal. Hay umbrales por dominio y decisión, condicionados por precio, pagabilidad, recuperación y costos evitables.
- Recuperación ausente en encajonante = **NO EVALUABLE**. No reemplazar por cero ni asignar automáticamente a botadero.
- Destino y valor condicional por bloque **no** prueban accesibilidad, precedencias, capacidad, pit, reservas, calendario ni VAN de la mina. S13 examinará restricciones.
- Cada visualización debe identificar operación/grupo, unidades, versión, alcance y si presenta resultado, proxy o hipótesis.

## 3. Misión S11 / P09 — aprender el criterio económico

**Pregunta gerencial:** ¿por qué el mismo material puede tener destinos razonables distintos según el estado de extracción, costos y escenario?

| Paso | Descubrimiento progresivo | Visualización que lo apoya | Comprobación conceptual |
|---|---|---|---|
| P09.1 | Un bloque de igual ley no tiene siempre igual valor; importa la decisión. | Visor S11: contexto y comparación de decisiones. | ¿Qué cambia cuando el material ya está minado? |
| P09.2 | Diferencia entre OPEX medio histórico y costo incremental evitable. | Tabla simple de costos aplicables por decisión. | ¿Por qué no vuelves a cobrar minado a material extraído? |
| P09.3 | Cutoff de extracción opcional vs cutoff de procesamiento ya minado, por dominio. | `fig-cutoff`: barras de umbral de ley. | ¿Por qué no hay un único cutoff? |
| P09.4 | Sensibilidad a precio, recuperación y costo de procesamiento. | Controles de escenario y cambio de barras, con unidades. | ¿Qué parámetro puede invertir una preferencia? |
| P09.5 | Interpretación de una regla condicionada, no una ley universal. | Comparación visual de dos escenarios predefinidos. | ¿Cuándo cambiarías de política? |
| P09.6 | Recomendación gerencial provisional. | Resumen humano: alternativa, driver, riesgo y condición de cambio. | ¿Qué recomendarías y con qué salvedad? |

**Ejemplo de diálogo, no texto rígido:**

> Kai: «Hoy vamos a decidir si conviene procesar cobre que ya está en superficie. El costo de extraerlo ya ocurrió; cobrarlo otra vez distorsionaría la decisión. En el gráfico tienes dos umbrales para la misma litología. ¿Cuál esperas que sea mayor: el de minado opcional o el de material ya extraído, y por qué?»

Cuando el estudiante responde correctamente, Kai explica el gráfico, introduce una sensibilidad y propone el siguiente razonamiento; no le pide localizar D08.

## 4. Misión S12 / P10 — comprender el valor por bloque

**Pregunta gerencial:** ¿qué conclusiones permite el modelo valorizado y cuáles todavía no autoriza?

| Paso | Descubrimiento progresivo | Visualización que lo apoya | Comprobación conceptual |
|---|---|---|---|
| P10.1 | Cada operación tiene un espacio de estudio de 9.408 bloques. | Visor: `fig-3d` y contexto topográfico no demostrado. | ¿Visualizar una lente sintética equivale a reservas? |
| P10.2 | Toneladas, ley y recuperación proxy determinan metal, no por sí solos valor. | Tabla de un bloque con valores y unidades. | ¿Por qué ley alta no asegura la mejor decisión? |
| P10.3 | El motor ya comparó decisiones condicionales: no extraer, extraer/procesar, botadero o stockpile, y destinos para material ya extraído. | Panel humano de valores por decisión para **un bloque**, sin JSON. | ¿Qué costos cambian entre estos dos estados? |
| P10.4 | El ejemplo de 120 bloques ilustra, pero el motor analiza **9.408**. | `fig-bank`, `fig-tonnage`, resumen de cobertura. | ¿Por qué no extrapolar una muestra sin control? |
| P10.5 | Agregados de masa/ley/metal/valor requieren tratar separadamente los no evaluables. | Dos tablas precomputadas por **destino condicional** del grupo con el motor existente; no es VAN. | ¿Por qué «no evaluable» no es waste? |
| P10.6 | La recomendación sigue siendo **preliminar**, pendiente de S13. | 3D + comparación de decisión y restricciones faltantes. | ¿Qué puede invalidar una decisión de bloque positivo? |

**Ejemplo de diálogo:**

> Kai: «El modelo ya está calculado, hermano; ahora toca pensar como gerentes. Observa este bloque: tiene toneladas, ley, recuperación proxy y costos de tres destinos. No tienes que programar ni buscar una celda. ¿Elegirías el destino solo por la ley o compararías el valor neto y las restricciones?»

## 5. Lo que existe y la brecha real

| Superficie | Actualmente disponible | Pendiente para experiencia sin fricción |
|---|---|---|
| S11 | `fig-cutoff`; precio, recuperación y costo editables; dos umbrales por dominio. | Conexión conversacional y presentación de escenarios con valores legibles. |
| S12 geología | 3D, mapa de bancos, histograma, curva tonelaje–ley, consulta de bloque. | Contextualización narrativa y selección de casos didácticos automáticos. |
| S12 economía | Motor `value_one` / `value_blocks` con valoración por destino, reporte docente privado y seis D09. | **Implementada** tabla por bloque con valores por decisión dentro del visor grupal, sin importar archivos. Pendiente QA de aula presencial. |
| S12 agregados | Motor `value_blocks` y seis datos sintéticos versionados; el visor ahora incorpora dos tablas de agregados condicionales por destino, masa, ley, cobre pagable y valor. | **Implementada** vista humana por grupo, sin resolver restricciones de S13. No es VAN, reservas ni decisión de pit. |
| Tutorización | Perfil Copilot `.github/agents/kai-gestion.agent.md` y contrato de memoria local ya incorporados. | **Pendiente:** prueba conversacional efectiva en PyCharm y comprobación de acceso a visualizadores del paquete individual. |

**No afirmar que algo se mostró o abrió si el agente no puede controlar el visor.** Decir «en la pestaña S11 observa…», salvo que exista una integración real que presente la gráfica. El contenido mostrado debe proceder del resultado preparado, no de valores imaginados.

## 6. Separación de seguridad y estado

- **Interno docente:** originales, parámetros, motores, reportes, soluciones, validación, manifiestos y CI. Se auditan y ejecutan antes de clase. No forman parte de las peticiones conversacionales al alumno.
- **Estudiante:** un caso/grupo; gráficos, tablas, 3D, preguntas de interpretación y decisiones. Nunca ZIP maestro ni reportes docentes.
- **Kai tutor:** estado conceptual por alumno y grupo (misión/paso, concepto adquirido, error, pista, siguiente pregunta). No confundir `COMPRENDIDO` con aprobación del gate de datos ni con calificación oficial.
- **Release:** Issue #11 sigue abierto hasta decisión docente expresa; los rótulos `PROPUESTA` / `NO OFICIAL` permanecen. No modificar modelos Inti v0.1, D01–D03, D08/D09 existentes ni sus hashes sin una versión nueva.

## 7. Aceptación del piloto

1. Alumno puede completar un recorrido P09 → P10 **sin buscar, crear, cargar o entregar archivos** y sin tocar Python/JSON.
2. Kai explica **para qué** se adoptó cada criterio; presenta una visualización por paso y pide solo una interpretación gerencial.
3. Ante un error, explica, cambia el ejemplo y reevalúa; no avanza hasta respuesta conceptual suficiente.
4. Dos alumnos de diferentes grupos no ven datos, parámetros ni soluciones reservadas del otro.
5. Un bloque sin recuperación permanece no evaluable; un bloque positivo no se anuncia como reserva, pit ni VAN.
6. El docente puede rastrear el número a código/versión, pero no convierte esa trazabilidad en tarea del alumno.
7. Ninguna prueba sintética o CI firma automáticamente D08/D09.

**Siguiente hito de aceptación:** revisar en navegador los seis visores generados con D08/D09 propuestos, documentar resultados; comprobar diálogo real Kai–estudiante en PyCharm. El motor Python `value_blocks` es la fuente de los agregados de P10; no se duplicó su cálculo en JS. La implementación y el QA técnico **no sustituyen** la ratificación docente del Issue #11.
