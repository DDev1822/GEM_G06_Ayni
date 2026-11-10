# Cierre de G06 · un ZIP para el profesor y un commit grupal

1. Cada estudiante guarda su Excel y ejecuta `EXPORTAR_MI_TRABAJO.cmd`; reúne todos los ZIP individuales por USB o carpeta compartida autorizada. Cada uno se importa por `CIERRE_GRUPAL.cmd` opción 1, que **no sobrescribe** sesiones ni mezcla grupos.
2. El representante elige opción 2 (Preparar); crea el cierre con los Excel recibidos. Si llega otro estudiante después, importa (opción 1) e incorpora (opción 3). El cierre anterior no se borra.
3. Completa el Excel grupal, fotografía/PDF las seis respuestas escritas **a mano** y agrega la evidencia a `cierre/2026-11-11/manuscrito/`; registra retroalimentación real de Kai y una captura del visor de G06 en sus carpetas. No inventes evidencias.
4. Opción 4 (Revisar) informa si faltan respuestas, decisiones o fotos. Si está incompleto, entrega igual: el estado queda INCOMPLETA, no aprobado.
5. Opción 5 crea un único ZIP docente **fuera del repositorio**, aun sin Git configurado y sin las seis respuestas. Incluye recibo con estado documental, pendientes, y SHA-256 al lado. Entrega este ZIP al profesor.
6. **Solo cuando el docente haya creado y configurado el repositorio privado**, y después de reunir las aportaciones del grupo, crea un único commit local con la opción 6, una sola vez. Para hacer un commit explícitamente INCOMPLETO se necesita `python scripts/lab01/cierre_grupal_v2.py commit --confirmar-representante --permitir-incompleta` con autorización del docente.
7. Si hay commit, el representante puede generar el ZIP *después* para incluir el recibo con SHA; si ya existe, no se sobrescribe y se debe conservar el primer archivo. El push remoto es aparte y solo con autenticación/permiso, usando `python scripts/lab01/cierre_grupal_v2.py push --confirmar-representante --autorizar-envio`.

**Preparación docente previa:** el docente crea un repositorio remoto vacío y privado, instala `gh` autenticado y ejecuta `configurar_repositorio_v2.py configurar --repo-url URL --rama main --confirmar-docente`; luego publica el commit de instalación con `publicar-inicial --autorizar-docente`. No hagas esto en el repositorio maestro.

Un commit no garantiza push. Un ZIP íntegro no demuestra comprensión ni nota aprobatoria. Kai guía, el equipo responde y el profesor valida.
