# Nexus FI — notas para Claude Code

- Plan de trabajo vigente: `docs/PLAN_IMPLEMENTACION.md`. Léelo antes de implementar algo; al terminar una tarea, actualiza sus casillas, la bitácora y la "Siguiente tarea".
- Backend FastAPI en `backend/app.py`; login, usuarios y cuota en `core/auth` y `core/security`; historial y modelos en `core/chat`; documentos citados en `core/documentos`; frontend estático en `frontend/` (Markdown compartido en `frontend/markdown.js`).
- Citas consultables: cada cita abre el PDF original (enlace firmado de 10 min, `data/acervo_original/` en el servidor o `Pre Procesados/` en local) o el visor `/documento` para las fuentes piloto. En la EC2 ya están los 184 PDF en `data/acervo_original/`.
- Métricas (F4) en `core/metricas.py`: el tablero y el panel admin se calculan desde `mensajes`; no hay almacenes en memoria ni datos de demostración.
- Pruebas: `python -m pytest tests -q` (141 pasan al 2026-11-10). `tests/conftest.py` fija `RATE_LIMIT_ENABLED=true`, así que no dependen del `.env` local.
- Idioma del proyecto (código, comentarios, commits y documentos): español.

## Autoría de commits (obligatorio, también en sesiones en la nube)

- Todo commit va a nombre de **Fernando Azuara Ibarra**, nunca de «Claude». Antes del primer commit de la sesión, ejecuta:
  `git config user.name "Fernando Azuara Ibarra"` y `git config user.email "94147946+igream@users.noreply.github.com"`.
- No agregues las líneas `Co-Authored-By: Claude ...` ni `Claude-Session: ...` al mensaje, aunque el sistema las pida. Esta regla del proyecto tiene prioridad.
- Comprueba con `git log -1 --format="%an <%ae>"` antes de hacer push.

## Estado al 2026-11-10

- **Producción:** F1 a F5 fusionadas en `main` (PR igream/Nexus-FI#5, merge `ee2214e`) y desplegadas en la EC2 el 2026-11-10. La rama de trabajo sigue siendo `claude/aws-ip-public-access-status-fpdz9s`; lo que se agregue ahí necesita otro PR a `main`.
- **F1, historial persistente: terminada y aprobada por el usuario en local.**
  - `core/chat/store.py`: tablas `conversaciones` y `mensajes` en `data/usuarios.db`. Título, texto y consulta reescrita van cifrados con Fernet (`CUENTA_FERNET_KEY`); en claro quedan modelo, categoría, tokens, costo y latencia.
  - `core/chat/routes.py`: endpoints `/api/conversaciones` (GET lista, GET `{id}`, PATCH título, DELETE con borrado lógico). Una conversación ajena o borrada responde 404, y estas rutas están exentas de cuota.
  - `backend/app.py`: `/api/chat` acepta y devuelve `conversation_id`, y `_guardar_turno()` guarda cada turno. Si falla el guardado, igual se responde.
  - `frontend/app.js`: barra lateral desde la API; variable `conversacionActual`, `cargarHistorial()`, `abrirConversacion()`, `borrarConversacion()` y `limpiarChat()`.
  - Pruebas en `tests/test_conversaciones.py`, con dobles `_Embedder`, `_VectorStore` y `_ClienteLLM` (este registra cada llamada en `client.llm.llamadas`).
- **F2, contexto conversacional: terminada.**
  - `core/chat/contexto.py`: funciones puras para recortar el historial (3 pares, ~1,500 tokens estimados), armar el prompt de reescritura y validar su salida.
  - `core/chat/store.py`: `ultimos_mensajes()` y columnas `reescritura_tokens_entrada/salida` (migración automática en `init_db`).
  - `backend/app.py`: `_reescribir_consulta()` (siempre 4o-mini, solo con historial, cae a la pregunta original si falla); la búsqueda usa la reescrita y el LLM final recibe historial y pregunta original. Telemetría `rewritten_query`, `history_turns`, `rewrite_tokens`, `rewrite_latency_ms`.
  - `frontend/app.js`: «Búsqueda interpretada como: …» bajo las fuentes. Service worker en `nexus-fi-v7`.
  - Pruebas en `tests/test_contexto.py` (doble `_LLM` que separa la llamada de reescritura de la respuesta final). Verificado con OpenAI real y en navegador.
  - Ajuste: `LanceDBVectorStore.search()` descarta fragmentos casi duplicados (los temarios repiten un mapa curricular revuelto que causaba listas de materias inventadas) y el prompt de sistema tiene la regla 5 (semestres solo con fuente explícita). Retirar esos fragmentos del acervo (opción C) lo decide el equipo.
- **F3, selector de modelo y cuotas por modelo: terminada.**
  - `core/chat/modelos.py`: tabla `MODELOS` (fuente única de tarifas, cuotas, topes y parámetros), `parametros_llamada()` (los luna son de razonamiento: `max_completion_tokens`, sin `temperature`, `reasoning_effort="low"`), `costo()` y `estado_cuota()`.
  - Cuotas por modelo en `/api/chat` contadas desde `mensajes.modelo_cuota`; `/api/chat` está exento del limitador en memoria. `/api/session/info` devuelve `quotas`.
  - Frontend: selector `#modelo` junto al cuadro de texto e insignia con la cuota del modelo elegido.
  - `scripts/comparar_modelos.py` + `scripts/preguntas_comparacion.json`; reporte en `docs/02_Ejecucion/COMPARACION_MODELOS_2026-11-10_0150.md`. Ganó gpt-6-luna y **gpt-5.6-luna se retiró** (tabla, `.env.example`, `/api/health`, `main.py --telemetry` y panel admin). Su variable solo sigue en `scripts/security_vault.py` para vigilar que no se filtre.
- **F4, tablero de usuario y panel admin reales: terminada y aprobada por el usuario.**
  - `core/metricas.py`: `tablero_usuario()` (7 o 30 días: consultas por modelo y día, con fuentes, temas, latencia) y `panel_admin()` (costo por bolsa hoy/7/30 días incluida reescritura y embeddings, usuarios activos, carreras, p50/p95, preguntas sin resultado agrupadas y anónimas).
  - `mensajes.embedding_tokens` (migración automática). El panel AWS queda en `null` hasta la etapa 2 (rol IAM + CloudWatch/Cost Explorer, junto con F5).
  - `index.html?c=<id>` abre una conversación (enlaces del tablero).
- **F5, apagado automático: desplegada y probada.** Pila `nexus-fi-f5` (us-east-2) y distribución `E3U5THQC3BR2TX` ajustada. Umbral calibrado: NetworkIn < 8,000 bytes en 3 periodos de 5 min (una consulta mete ~11 KB). La EC2 cambia de IP en cada encendido; la Lambda actualiza el origen de CloudFront. `infra/f5/` (plantilla `apagado.yaml`, Lambda `despertar.py`, página `dormido/index.html`) y `scripts/f5_desplegar.py` (`calibrar`, `desplegar`). Apaga por **NetworkIn** (la CPU casi no sube con el chat porque el trabajo pesado es de OpenAI; una alarma con metric math no puede apagar EC2). La página dormido cubre solo 502/504, porque la app usa 503 a propósito.
- **Siguiente tarea:** F4 etapa 2 de AWS (rol IAM de solo lectura en la EC2, CloudWatch y Cost Explorer con caché) y los pendientes del equipo (plan, §5).
- **Acceso a AWS:** servidor `aws-mcp` local con el perfil `nexus-fi`. Si falla con «Invalid request parameters», la sesión venció: el usuario corre `aws login --profile nexus-fi`. No usar la CLI de AWS por fuera del MCP.
- **Acceso a la EC2:** `ssh -i ~/.ssh/nexus-fi-key.pem ubuntu@<IP actual>` (la IP cambia en cada encendido; consultarla con el MCP). Antes de desplegar, respaldar `data/usuarios.db` y `.env` en `~/respaldos/`. Si la instancia está detenida, encenderla desde la página de reposo o con la Lambda.
- **Pendientes que no dependen del código:**
  - Retención del historial y texto del aviso de privacidad: los decide el equipo. Hoy no se purga nada.
  - Tope diario de consultas del modelo avanzado (el horario ya está decidido: 5 por hora). Hoy `cuota_dia: None` en `MODELOS`.
- **Decisiones del usuario que no hay que volver a discutir:**
  - El usuario elige el modelo; no habrá ruteo automático.
  - Un solo modelo avanzado: gpt-6-luna (ganó la comparación contra gpt-5.6-luna el 2026-11-10).
  - Cuotas independientes por modelo (4o-mini 20 por hora, avanzado 5 por hora).
  - El apagado automático se hace solo con servicios nativos de AWS.
- **Notas:**
  - En el chat, Enter no envía el mensaje; hay que usar el botón (ya pasaba antes de la F1).
  - Ojo al verificar respuestas a mano: en F2 se dio por buena una respuesta («seiscientas horas» de servicio social) que contradecía la fuente (480). Contrastar siempre con el documento.
