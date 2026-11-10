# Nexus FI — notas para Claude Code

- Plan de trabajo vigente: `docs/PLAN_IMPLEMENTACION.md`. Léelo antes de implementar algo; al terminar una tarea, actualiza sus casillas, la bitácora y la "Siguiente tarea".
- Backend FastAPI en `backend/app.py`; login, usuarios y cuota en `core/auth` y `core/security`; historial en `core/chat`; frontend estático en `frontend/`.
- Pruebas: `python -m pytest tests -q` (62 pasan al 2026-11-10).
- Idioma del proyecto (código, comentarios, commits y documentos): español.

## Estado al 2026-11-10 (traspaso de la sesión en la nube a la sesión local)

- **Rama de trabajo:** `claude/aws-ip-public-access-status-fpdz9s` (subida a GitHub; sin PR todavía). Contiene el plan y la fase F1.
- **F1, historial persistente: terminada.**
  - `core/chat/store.py`: tablas `conversaciones` y `mensajes` en `data/usuarios.db`. Título, texto y consulta reescrita van cifrados con Fernet (`CUENTA_FERNET_KEY`); en claro quedan modelo, categoría, tokens, costo y latencia.
  - `core/chat/routes.py`: endpoints `/api/conversaciones` (GET lista, GET `{id}`, PATCH título, DELETE con borrado lógico). Una conversación ajena o borrada responde 404, y estas rutas están exentas de cuota.
  - `backend/app.py`: `/api/chat` acepta y devuelve `conversation_id`, y `_guardar_turno()` guarda cada turno. Si falla el guardado, igual se responde.
  - `frontend/app.js`: barra lateral desde la API; variable `conversacionActual`, `cargarHistorial()`, `abrirConversacion()`, `borrarConversacion()` y `limpiarChat()`. Service worker en `nexus-fi-v6`.
  - Pruebas en `tests/test_conversaciones.py`, con dobles `_Embedder`, `_VectorStore` y `_ClienteLLM` (este registra cada llamada en `client.llm.llamadas`).
  - Verificado con pytest y en navegador con dobles. **Falta probarlo contra OpenAI real y en la EC2**; el usuario lo va a probar en local.
- **Siguiente tarea: F2, contexto conversacional.**
  - Incluir los últimos N turnos (propuesta: 3 pares, unos 1,500 tokens) en los `messages` de `/api/chat`.
  - Reescribir la pregunta de seguimiento con 4o-mini antes del embedding, solo si hay historial. Guardarla con `agregar_mensaje(..., consulta_reescrita=...)`; si la reescritura falla, usar la pregunta original.
  - Detalle y pruebas en el plan, §F2.
- **Pendientes que no dependen del código:**
  - Retención del historial y texto del aviso de privacidad: los decide el equipo. Hoy no se purga nada.
  - IDs, precios y parámetros de `gpt-6-luna` y `gpt-5.6-luna`: verificarlos en developers.openai.com antes de la F3. Desde la nube estaba bloqueado; en local, consultarlos.
  - Tope diario de consultas del modelo avanzado (el horario ya está decidido: 5 por hora).
  - F5 (apagado automático de la EC2): requiere acceso a AWS. El usuario tenía problemas para iniciar sesión con IAM desde el celular; ver el plan, §F5.
- **Decisiones del usuario que no hay que volver a discutir:**
  - El usuario elige el modelo; no habrá ruteo automático.
  - Un solo modelo avanzado: probablemente gpt-6-luna, tras compararlo con gpt-5.6-luna.
  - Cuotas independientes por modelo (4o-mini 20 por hora, avanzado 5 por hora).
  - El apagado automático se hace solo con servicios nativos de AWS.
- **Notas:**
  - En el chat, Enter no envía el mensaje; hay que usar el botón (ya pasaba antes de la F1).
  - `backend/app.py:554` sigue fijando `gpt-4o-mini` como modelo. Se corrige en la F3.
