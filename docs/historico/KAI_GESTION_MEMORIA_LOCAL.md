# Kai Gestión — memoria local del recorrido conceptual (Copilot PyCharm)

**Uso:** continuidad del aprendizaje por alumno/grupo; no es un sistema de calificación ni de ejecución. La carpeta de cada estudiante se crea **localmente** sólo en el equipo autorizado. Está excluida del control Git. Nunca colocar esta memoria dentro de un ZIP de otro grupo.

## Directorio y regla mínima

- Carpeta privada (ignorada por Git): `.kai_gestion_local/alumnos/`.
- Nombre: alias breve validado, por ejemplo `luis-p2.md`, sin correo, DNI, nombre completo ni identificación sensible.
- Un alumno = una ficha, un grupo G01–G06 por recorrido; si cambia de grupo, confirmar explícitamente antes de usar otro caso.
- Nunca leer ni alterar fichas de otros alumnos. No mezclar los datos de las seis operaciones.
- Registrar **solamente** conceptos comprendidos, dificultades pedagógicas y próximo paso. No almacenar transcripciones largas, notas privadas, calificaciones ni resultados confidenciales.
- Escribir sólo si el estudiante autoriza la memoria por defecto en la sesión y no ordena no guardar. Si pide «no guardes», sólo trabajar en el contexto actual y no escribir.
- Conservar archivos existentes: editar únicamente campos necesarios. Después de escribir, **releer** y confirmar; nunca afirmar actualización si el IDE no la aplicó.

## Estructura recomendada de ficha (Markdown, sin JSON)

```markdown
# Progreso conceptual — Kai Gestión
Alias: luis-p2
Grupo: G04
Operación: Tikari Copper
Programa: Gestión de Empresas Mineras — UPN 2026-2
Estado de recorrido: EN_APRENDIZAJE
Misión actual: S11/P09
Paso actual: P09.1
Conceptos comprendidos: ninguno registrado todavía
Última respuesta evaluada: pendiente
Dificultad actual: ninguna identificada
Pregunta siguiente: ¿Por qué cambia el costo relevante cuando el material ya se extrajo?
Actualizado por: conversación Copilot (fecha sólo si disponible)
Observación: D08/D09 docentes aún no oficiales; comprensión ≠ aprobación formal.
```

## Transiciones de progreso

`EN_APRENDIZAJE` mientras la respuesta sea incorrecta o insuficiente; `COMPRENDIDO` para el concepto específico cuando el alumno ofrece razonamiento técnicamente suficiente. Al acertar P09.1 se inicia P09.2 en la misma conversación; al completar P09.6 se inicia P10.1. El agente no obliga a aportar CSV, hojas, capturas ni scripts; la única barrera del recorrido es conceptual.

**No usar** estados `NEEDS_EVIDENCE` del tutor Planeamiento para impedir el avance aquí. Gate T3 y calificación académica del docente son procesos independientes y nunca se modifican desde esta ficha.

## Control de reinicio y continuidad

Si no hay ficha: iniciar en P09.1 y no afirmar que existe avance previo. Si hay ficha: comprobar que corresponde al alias y grupo; retomar el paso sin repetir una lección ya comprendida. Si existe una discrepancia, pedir sólo la aclaración mínima; no crear nuevos datos. La revisión interna de docentes puede seguir usando manifiestos, QA y resultados, pero nunca se convierte en trabajo del estudiante.
