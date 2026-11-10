# Plan de implementación — Nexus FI (post-piloto)

Documento de trabajo para las sesiones de desarrollo con Claude Code. Antes de empezar una tarea:
1. Lee este archivo completo.
2. Revisa **Siguiente tarea** y la **Bitácora**.
3. Al terminar, marca las casillas, actualiza la bitácora y la siguiente tarea, y haz commit de este archivo con el código.

Última actualización: 2026-11-10 (F1 a F4 terminadas; estado de traspaso en `CLAUDE.md`).

---

## 1. Estado actual (diagnóstico del 2026-11-10)

| Área | Situación | Dónde |
| :--- | :--- | :--- |
| Modelo del chat | Siempre se llama a `gpt-4o-mini`. El nombre está fijo aunque se elija otro cliente o clave, y el frontend nunca envía `model`. | `backend/app.py:554`, `frontend/app.js:532` |
| Costos por modelo | Solo existen las tarifas de 4o-mini, que se aplican a cualquier modelo. | `backend/app.py:142-146`, `:589-593` |
| Historial | No existe. Los tres elementos de la barra lateral están escritos a mano. | `frontend/index.html:32-34` |
| Contexto | Cada consulta se envía sola (prompt de sistema y pregunta actual), sin turnos previos. | `backend/app.py:578-584` |
| Cuota | Es la misma para todo: 20 por hora y 60 por día. Vive en memoria y se pierde al reiniciar. El middleware decide antes de leer el cuerpo, así que no conoce el modelo. | `core/security/rate_limiter.py` |
| Tablero de usuario | El endpoint no pide sesión, muestra métricas globales y no por usuario, guarda en memoria y arranca con datos de demostración (`baseline_demo`). | `backend/app.py:119-133`, `:389-403`, `frontend/dashboard.html` |
| Panel admin | Los tokens se cuentan en memoria, encima de datos de demostración. Los datos de AWS están fijos y son incorrectos ("2x t3.medium"; la real es una t3.small). | `backend/app.py:135-140`, `:406-430` |
| Base de datos | SQLite en `data/usuarios.db`, montada como volumen, con las tablas `cuentas_autorizadas` y `usuarios`. `request.state.user_id` es el `sub` del token. | `core/auth/store.py`, `core/auth/middleware.py:24` |
| Infraestructura | Una EC2 t3.small en us-east-2 con docker compose (backend y nginx), detrás de CloudFront (`d2j5rd06t9r4yq.cloudfront.net`). No se apaga sola. | `README.md` §Despliegue |
| Pruebas | Con pytest, en `tests/`; se corren con `python -m pytest tests -q`. | — |

---

## 2. Decisiones del equipo

- **D1. Modelos:** el **usuario elige** el modelo en la interfaz. No habrá ruteo automático por ahora.
- **D2. Modelos disponibles:** `gpt-4o-mini` como modelo rápido y **un solo** modelo avanzado. Se comparan `gpt-6-luna` y `gpt-5.6-luna` y se queda el ganador; el candidato favorito es gpt-6-luna. Referencias: developers.openai.com/api/docs/models/gpt-6-luna y developers.openai.com/api/docs/models/gpt-5.6-luna.
- **D3. Cuotas independientes por modelo**, en número de consultas y con tope de salida:
  - 4o-mini: 20 por hora (y 60 por día).
  - Avanzado: 5 por hora (el tope diario está por definir).
- **D4. Historial** persistente por usuario, con listar, abrir y borrar.
- **D5. Contexto conversacional** con reescritura de la pregunta antes de la búsqueda vectorial.
- **D6. Tablero y panel admin** con datos reales calculados desde la base. Se eliminan los datos de demostración.
- **D7. Apagado automático** solo con servicios nativos de AWS (CloudWatch, EventBridge, Lambda, S3 y CloudFront). Nada de servicios externos.

---

## 3. Fases

Orden: F1 → F2 → F3 → F4. F5 es infraestructura y puede avanzar en paralelo cuando haya acceso a AWS.

### F1. Historial persistente (base de F2, F3 y F4) — ✅ terminada el 2026-11-10

Implementada en `core/chat/` (`store.py` y `routes.py`), `backend/app.py` (`_guardar_turno` y `conversation_id` en `/api/chat`) y `frontend/app.js`. Respecto al esquema propuesto abajo, en la versión final el título también va cifrado (`titulo_cifrado`), igual que el contenido y la consulta reescrita; las citas se guardan en `citas_json`.

**Esquema** (en `core/` o un módulo nuevo `core/chat/store.py`, sobre la misma `data/usuarios.db`, creado en `init_db`):

```sql
CREATE TABLE IF NOT EXISTS conversaciones(
  id TEXT PRIMARY KEY,               -- uuid4
  usuario_id TEXT NOT NULL,          -- request.state.user_id
  titulo TEXT,                       -- primeras ~60 letras de la primera pregunta
  creada_en TEXT NOT NULL,
  actualizada_en TEXT NOT NULL,
  eliminada INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS mensajes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversacion_id TEXT NOT NULL REFERENCES conversaciones(id),
  usuario_id TEXT NOT NULL,
  rol TEXT NOT NULL CHECK(rol IN ('user','assistant')),
  contenido TEXT NOT NULL,           -- cifrado con store.cifrar()
  consulta_reescrita TEXT,           -- F2
  modelo TEXT,                       -- F3
  categoria_principal TEXT,          -- categoría de la cita top; para el tablero
  encontrado INTEGER,                -- found de la respuesta
  tokens_entrada INTEGER, tokens_salida INTEGER, costo_usd REAL, latencia_ms REAL,
  creado_en TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_msg_usuario_fecha ON mensajes(usuario_id, creado_en);
```

**Tareas:**
- [x] Crear el módulo de almacenamiento con estas funciones: crear conversación, agregar mensaje, listar conversaciones, obtener conversación y borrar (borrado lógico).
- [x] `/api/chat`:
  - Aceptar `conversation_id` opcional. Si no viene, crear una conversación nueva.
  - Guardar el mensaje del usuario y el del asistente con su telemetría.
  - Devolver `conversation_id`.
- [x] Endpoints, todos con sesión y solo sobre conversaciones del propio usuario:
  - `GET /api/conversaciones`
  - `GET /api/conversaciones/{id}`
  - `DELETE /api/conversaciones/{id}`
  - `PATCH /api/conversaciones/{id}` (título)
- [x] Frontend:
  - Barra lateral cargada desde la API.
  - Abrir una conversación pinta sus mensajes.
  - "Nueva consulta" reinicia `conversation_id`.
  - Botón para borrar.
- [x] Quitar los elementos fijos de `index.html:32-34`.
- [ ] Decidir y documentar la retención (propuesta: 90 días) y una línea en el aviso de privacidad. **Pendiente de decisión del equipo; hoy no se purga nada.**

**Pruebas** (`tests/test_conversaciones.py`, con el LLM y el embedder simulados):
- [x] Una consulta sin `conversation_id` crea una conversación, y una segunda con el id la reutiliza.
- [x] El usuario B recibe 404 al pedir o borrar una conversación del usuario A.
- [x] Una conversación borrada no aparece en el listado.
- [x] Los datos persisten al reabrir la conexión (simula un reinicio).
- [x] El contenido queda cifrado en la tabla.

### F2. Contexto conversacional — ✅ terminada el 2026-11-10

Implementada en `core/chat/contexto.py` (funciones puras: `recortar_historial`, `mensajes_reescritura`, `limpiar_reescritura`), `core/chat/store.py` (`ultimos_mensajes` y dos columnas nuevas) y `backend/app.py` (`_reescribir_consulta` y el paso 0 de `/api/chat`). Los tokens se **estiman** (3.5 caracteres por token) en lugar de usar `tiktoken`, que descarga su codificación la primera vez y podría fallar en plena consulta.

**Tareas:**
- [x] Al responder, incluir los últimos N turnos de la conversación (3 pares de pregunta y respuesta, recortados a unos 1,500 tokens; se descartan primero los más viejos y, si ni el último cabe, se recorta su respuesta) entre el prompt de sistema y la pregunta actual.
- [x] **Reescritura de la pregunta:** solo si hay historial, hacer una llamada a `gpt-4o-mini` (temperature 0, máximo 100 tokens) que convierta la pregunta de seguimiento en una pregunta autónoma.
  - El embedding y la búsqueda en LanceDB (incluido el filtro de nombres propios) usan la versión reescrita; al LLM final se le pasan el historial y la pregunta original.
  - Guardar la reescritura en `mensajes.consulta_reescrita_cifrada` (cifrada, como el resto del texto).
  - Si la reescritura falla, sale vacía o mide más de 400 caracteres, usar la pregunta original.
- [x] Contar los tokens de la reescritura en la bolsa de 4o-mini. Además se guardan aparte en `mensajes.reescritura_tokens_entrada` y `reescritura_tokens_salida` (migración automática en `init_db`), para que en F3/F4 no se mezclen con los del modelo avanzado.
- [x] Mostrar la reescritura en la telemetría: `rewritten_query`, `history_turns`, `rewrite_tokens` y `rewrite_latency_ms`; en el chat, «Búsqueda interpretada como: …» y el número de turnos previos. Service worker en `nexus-fi-v7`.

**Pruebas** (`tests/test_contexto.py`):
- [x] Sin historial no hay llamada de reescritura.
- [x] Con historial, los `messages` enviados al LLM incluyen los turnos previos en orden y respetan el límite N.
- [x] Prueba manual (OpenAI real, base temporal y cuenta ficticia): "¿Qué requisitos tiene el servicio social?" y luego "¿y cuál es el plazo?" se reescribió como "¿Cuál es el plazo para realizar el servicio social?" y recuperó el Reglamento del Servicio Social (Art. 44). En el navegador, "¿y cuántas horas son?" recuperó el Art. 16, **pero la respuesta decía «seiscientas horas» y el reglamento dice 480**: la reescritura y las fuentes eran correctas y el error fue del modelo al redactar. Se detectó en F3 con la comparación, donde los tres modelos responden 480.
- [x] Una falla en la reescritura no rompe la respuesta.
- [x] Extra: reescritura inservible, guardado cifrado con tokens, consulta sin resultados con contexto, recorte por tokens y limpieza de la salida.

**Ajuste tras la revisión del usuario (alucinación en una primera consulta, sin historial):**
«Que materias se dan en el sexto semestre de ingenieria en computación?» (sin acentos) recuperó cuatro copias del **mapa curricular** que traen incrustado los temarios, extraído como una lista de materias revuelta. El horario del 6.º quedó en sexto lugar (0.614 contra 0.628) y el LLM armó una lista inventada. Hay 115 fragmentos así en 41 temarios.
- [x] **A.** `LanceDBVectorStore.search()` descarta candidatos casi duplicados (Jaccard ≥ 0.80 sobre las palabras sin el encabezado; solo fragmentos de 30 palabras distintas o más). Pide 3 veces más candidatos (mínimo 12) para reponerlos. Se desactiva con `quitar_duplicados=False`.
- [x] **B.** Regla 5 del prompt de sistema: solo asignar materias a un semestre si la fuente lo dice de forma explícita; las tablas revueltas no cuentan.
- [x] Pruebas en `tests/test_busqueda_terminos.py` (copias del mapa, sin filtro, fragmentos cortos). Verificado con OpenAI real: la misma pregunta ahora responde con las 6 materias de `horarios_ico_semestre_6.md`.
- [ ] **C (pendiente de decisión del equipo):** retirar del acervo los 115 fragmentos del mapa revuelto, como cambio técnico (al estilo de CT-01), y, si existe una versión limpia del mapa curricular, agregarla como documento estructurado.

### F3. Selector de modelo y cuotas por modelo — ✅ terminada el 2026-11-10

Implementada en `core/chat/modelos.py` (tabla `MODELOS`, `parametros_llamada`, `costo`, `estado_cuota`), `core/chat/store.py` (`contar_consultas` y columna `modelo_cuota`), `backend/app.py` (validación, cuota y llamada en `/api/chat`; `cuota_modelo` y `quotas` en `/api/session/info`) y `frontend/` (selector y cuota). Service worker en `nexus-fi-v8`.

**Antes de programar** (verificado el 2026-11-10 en developers.openai.com y con llamadas reales):
- [x] Identificadores: `gpt-6-luna` y `gpt-5.6-luna` (un solo snapshot cada uno). Precio por millón de tokens: gpt-6-luna 0.10 entrada / 0.01 en caché / 0.50 salida; gpt-5.6-luna 0.20 / 0.02 / 1.20 (gpt-4o-mini: 0.15 / 0.60). Los dos admiten Chat Completions y Responses; se sigue con Chat Completions.
- [x] Parámetros: son modelos de razonamiento. Rechazan `max_tokens` (hay que usar `max_completion_tokens`, que incluye el razonamiento) y solo aceptan `temperature` con `reasoning_effort="none"`. Se usa `reasoning_effort="low"`.

**Comparación gpt-6-luna vs gpt-5.6-luna** (con gpt-4o-mini como referencia):
- [x] Script `scripts/comparar_modelos.py` con 20 preguntas de `scripts/preguntas_comparacion.json` (hechos verificados en el acervo; 2 fuera de tema). Pasa por el mismo flujo de `/api/chat`, con base temporal y cuenta ficticia.
- [x] Resultado en `docs/02_Ejecucion/COMPARACION_MODELOS_2026-11-10_0150.md`:

  | Modelo | Aciertos | Latencia LLM mediana | Costo por consulta |
  | :--- | :---: | :---: | :---: |
  | gpt-4o-mini | 17/20 | 2,452 ms | 0.00039 USD |
  | **gpt-6-luna** (low) | 17/20 | 2,127 ms | **0.00026 USD** |
  | gpt-5.6-luna (low) | 17/20 | 2,062 ms | 0.00060 USD |

  Las tres fallas (titulación, décimo semestre, coordinadora) son iguales en los tres modelos y vienen de la búsqueda, no del modelo. **gpt-6-luna gana:** mismos aciertos, latencia similar y menos de la mitad del costo de gpt-5.6-luna (y más barato que 4o-mini).
- [x] gpt-5.6-luna retirado con la confirmación del usuario: tabla `MODELOS`, `.env.example`, `/api/health`, `main.py --telemetry` y la tarjeta y la bolsa `luna56` del panel admin. Pedirlo ahora da 422. La variable `OPENAI_API_KEY_GPT5_6_LUNA` sigue en la lista de `scripts/security_vault.py` para detectarla si queda en algún `.env`.

**Tareas:**
- [x] Llamar al modelo elegido, no al fijo.
- [x] Tabla única `MODELOS` con id de API, claves, bolsa, tarifas, tope de salida, cuota por hora y por día, y parámetros admitidos.
- [x] Validar `model` contra esa tabla: 422 si no existe; 503 si existe pero no tiene clave en el servidor.
- [x] **Cuotas por modelo:**
  - `/api/chat` sale del limitador en memoria (`QUOTA_EXEMPT_PREFIXES`) y se verifica en el endpoint, antes del embedding.
  - Se cuentan las respuestas de `mensajes` por `usuario_id`, `modelo_cuota` (el modelo que pidió el usuario; la migración marca los mensajes viejos como 4o-mini) y `creado_en`. Sobreviven a reinicios y borrar una conversación no devuelve cuota.
  - El 429 dice qué modelo se agotó, sus límites, `retry_after` y `reset_at`.
  - Limitación aceptada para el piloto: la consulta se cuenta al guardarse, así que dos consultas simultáneas justo en el límite podrían pasar ambas. Las consultas sin resultados (respaldo sin LLM) también cuentan.
- [x] Tope de salida: 4o-mini 1,200 (`max_tokens`); avanzado 2,000 (`max_completion_tokens`, incluye razonamiento; en la comparación el promedio de salida fue de 87 tokens).
- [x] `/api/session/info` devuelve `quotas` (por modelo del selector, con `available`), `default_model` y `quota` (la de 4o-mini, por compatibilidad).
- [x] Frontend: selector junto al cuadro de texto (opciones desde `quotas`, recuerda la elección en `localStorage`), insignia con la cuota del modelo elegido, «Avanzado (agotado)» desactivado y el mensaje del 429 tal como lo manda el servidor. Ajustado para celular.

**Pruebas** (`tests/test_modelos.py`, 16 nuevas):
- [x] El modelo enviado a la API es el elegido, con sus parámetros (cliente simulado).
- [x] Un modelo inválido da 422; uno sin clave, 503.
- [x] Al agotar el avanzado (5 por hora) llega un 429 para él mientras 4o-mini sigue disponible, y viceversa; la cuota es por usuario.
- [x] Las cuotas se conservan tras reabrir la base, y borrar conversaciones no las devuelve.
- [x] El costo registrado usa la tarifa del modelo correcto.
- [x] La reescritura de F2 sigue usando 4o-mini aunque se elija el avanzado.
- [x] `tests/test_rate_limiter.py` no necesitó cambios (su interfaz no cambió).
- [x] Verificado en navegador (instancia con base temporal y cuenta ficticia, OpenAI real): respuesta con gpt-6-luna, insignia «Avanzado 4/5», 429 al agotar el avanzado mientras 4o-mini responde y opción «Avanzado (agotado)» desactivada.

**Ajustes tras la revisión del usuario:**
- [x] **Tablas en el chat:** `renderMarkdown()` (frontend) convierte tablas Markdown (encabezado, fila `|---|` con alineación y filas) en `<table>` con desplazamiento horizontal en celular; regla 6 del prompt para usarlas con datos de varias columnas.
- [x] **Salida del avanzado:** `max_salida` de gpt-6-luna pasa a 6,000 (5 veces los 1,200 de 4o-mini) y cada modelo lleva su `estilo` en `MODELOS`, que entra en la regla 1 del prompt: el rápido responde conciso y el avanzado completo y detallado. Verificado con OpenAI real: la pregunta de Compiladores sale con dos tablas y el horario coincide con `horarios_ico_semestre_6.md`.
- [x] **Citas consultables:** se revisaron las referencias [1]-[29] del Documento Maestro de Ejecución y solo 3 de 29 enlaces responden (las dos de SIBecas y la portada de cj.uaemex.mx); los PDF de reglamentos de `cj.uaemex.mx/images/...` dan 404 y las fuentes piloto no tienen enlace público. El usuario eligió **servir los documentos dentro de la app**:
  - `core/documentos/catalogo.py`: catálogo armado al arrancar desde el frontmatter de `Procesados/` (`archivo_fuente`); relaciona los 198 documentos de LanceDB con su original sin regenerar embeddings.
  - `core/documentos/routes.py`: `POST /api/documentos/{id}/enlace` (con sesión) da un enlace HMAC que vence en 10 minutos; `GET .../archivo` sirve el PDF `inline`; `GET .../texto` (con sesión) da el texto para el visor. Solo acepta ids del catálogo; los `.html` originales nunca se sirven; si falta el PDF se cae al texto. Exento de cuota.
  - Cada cita trae `doc_id`; el historial lo completa en conversaciones viejas. En el chat la cita es un enlace que abre el PDF en la página citada (`#page=N`) o el visor `/documento` (fuentes piloto). `renderMarkdown` pasó a `frontend/markdown.js`, compartido con el visor.
  - Originales en `data/acervo_original/` (`scripts/preparar_acervo_original.py`: 184 PDF, 235.9 MB) o, en local, en `Pre Procesados/`. **Pendiente: subirlos a la EC2** (README, §Despliegue).
  - 13 pruebas en `tests/test_documentos.py`. Verificado en navegador: enlace 200, PDF de 2.3 MB `inline`, enlace vencido 403, visor del horario con su tabla.
- [ ] **Documento Maestro v2.0:** corregir las referencias [1]-[29] (26 enlaces rotos). El usuario confirma que los propios portales universitarios no funcionan como deberían, así que conviene citar la ruta que sí abre, o indicar que el documento se consulta desde Nexus FI.
- [ ] Hueco del acervo: en `6to_PE_ICO_COMPILADORES` (y probablemente en otros temarios) la extracción perdió los números de horas y créditos de la tabla de carga académica.

### F4. Tablero de usuario y panel admin reales — ✅ terminada el 2026-11-10 (falta la etapa 2 de AWS)

Implementada en `core/metricas.py` (`tablero_usuario`, `panel_admin`, `percentil`), `backend/app.py` (los dos endpoints y `_acervo`), `core/chat/store.py` (columna `embedding_tokens` e índice por fecha) y las páginas `frontend/dashboard.html` y `frontend/admin-metrics.html`. Las fechas se agrupan en hora del centro de México (UTC−6).

**Tablero de usuario** (`/api/v1/metrics/user-dashboard?dias=7|30`, con sesión y solo datos propios):
- [x] Consultas totales y por modelo, por día de los últimos 7 y 30 (barras apiladas por modelo).
- [x] Cuota restante por modelo, con hora de liberación.
- [x] Temas frecuentes (`categoria_principal`) y porcentaje de respuestas con fuentes.
- [x] Latencia promedio.
- [x] Últimas conversaciones con enlace (`index.html?c=<id>` abre la conversación en el chat).
- [x] Documentos y fragmentos reales del acervo (se quitó el «3,977» fijo).

**Panel admin** (`/api/v1/admin/metrics`, solo administradores):
- [x] Tokens y costo por bolsa (modelo de respuesta, reescritura de 4o-mini y embeddings) para hoy, 7 y 30 días, y serie diaria de costo y consultas. Los tokens de embedding se guardan ahora en `mensajes.embedding_tokens`; los mensajes anteriores a F4 no los tienen (cuentan como 0, una fracción de centavo).
- [x] Usuarios activos y consultas por carrera.
- [x] Consultas sin resultado (`encontrado = 0`): tasa y últimas preguntas agrupadas con su número de repeticiones, sin decir quién las hizo.
- [x] Latencia p50 y p95.
- [x] Sección AWS sin valores fijos (`aws: null` y una nota en la página).
- [ ] **Etapa 2 de AWS:** CloudWatch (CPU y estado de la instancia) y Cost Explorer (0.01 USD por llamada; caché de unas 6 horas). Requiere darle un rol IAM a la instancia, así que va junto con F5.
- [x] Eliminados `user_metrics_store`, `admin_tokens_store`, `record_query_metrics`, `record_token_usage` y los textos `baseline_demo`, y los valores de respaldo inventados de ambas páginas.

**Pruebas** (`tests/test_metricas.py`, 14 nuevas):
- [x] El tablero exige sesión; periodo inválido da 422.
- [x] Dos usuarios ven datos distintos.
- [x] Un usuario sin rol de admin recibe 403 en el panel (y 401 sin sesión).
- [x] Los totales coinciden con los mensajes sembrados (por periodo, bolsa, carrera, latencias y preguntas sin resultado).
- [x] La consulta guarda los tokens del embedding; percentiles.
- [x] Verificado en navegador con la cuenta ficticia: tablero (consultas por modelo, cuotas, temas, enlaces que abren la conversación) y panel admin (costo por bolsa, p50/p95, preguntas sin resultado agrupadas), también a 375 px de ancho.

### F5. Apagado automático (infraestructura, solo servicios nativos de AWS)

**Requisito previo:** acceso a la cuenta. Desde el celular:
- Iniciar sesión con usuario IAM, en el navegador en modo escritorio, con la URL `https://<ID-de-cuenta>.signin.aws.amazon.com/console`.
- En la app de AWS: Agregar identidad → usuario IAM (ID de cuenta, usuario y contraseña).
- Que el usuario raíz entre por us-east-1 no indica que sea otra cuenta. Es la misma; solo hay que cambiar la región a us-east-2.

**Tareas:**
- [ ] Revisar la instancia: ID, si tiene IP elástica, DNS público y el origen de CloudFront.
- [ ] **Apagado:** alarma de CloudWatch `CPUUtilization < ~3 %` (promedio de 5 minutos) durante 3 periodos (15 minutos), con la acción nativa `arn:aws:automate:us-east-2:ec2:stop`. Calibrar el umbral midiendo la CPU en reposo.
- [ ] **Encendido:** Lambda `nexus-despertar` con Function URL. Hace dos cosas:
  - Ejecuta `StartInstances`.
  - Si el DNS público cambió, actualiza el origen de CloudFront.

  Protegerla con un token simple y el permiso mínimo: `ec2:StartInstances` y `ec2:DescribeInstances` sobre esa instancia, y `cloudfront:GetDistributionConfig` y `UpdateDistribution` sobre esa distribución.
- [ ] **Página "servidor dormido":** HTML estático en S3 como origen secundario de CloudFront, servido como página de error personalizada para 502, 503 y 504. Lleva un botón que llama a la Lambda y recarga cuando `/health` responde.
- [ ] Alternativa, si actualizar el origen da problemas: IP elástica (unos 3.6 USD al mes) y dejar el origen fijo.
- [ ] Opcional: regla de EventBridge Scheduler para detenerla todas las noches.
- [ ] Documentar el procedimiento en el README.

**Pruebas:**
- [ ] Sin tráfico, la instancia queda `stopped` en unos 15-20 minutos.
- [ ] Con la instancia detenida, la URL de CloudFront muestra la página "dormido".
- [ ] El botón la arranca y en unos 2 minutos `/health` responde 200 por CloudFront.
- [ ] La Lambda rechaza llamadas sin token.

---

## 4. Pendientes por verificar

- [x] Identificadores, precios y parámetros de gpt-6-luna y gpt-5.6-luna (§F3).
- [ ] Huecos de recuperación detectados por la comparación: opciones de titulación (sale la Guía de Trámites en vez del Reglamento de Evaluación Profesional), «décimo semestre» (no recupera `horarios_ico_semestre_10`) y nombre de la coordinadora (solo está en el encabezado de los horarios).
- [ ] Acceso a AWS desde la sesión: el conector de AWS necesita volver a autenticarse en la configuración de conectores de claude.ai, o hay que darle a la sesión una clave IAM.
- [ ] Tope diario del modelo avanzado.
- [ ] Retención del historial y texto del aviso de privacidad.
- [ ] Retirar del acervo los fragmentos del mapa curricular revuelto (§F2, opción C).

## 5. Siguiente tarea

**F5: apagado automático de la EC2** (más la etapa 2 de AWS del panel admin, que necesita el mismo rol IAM). Requiere acceso a la cuenta de AWS: el conector de AWS de esta sesión no se pudo conectar. En el mismo viaje a la instancia hay que subir `data/acervo_original` (README, §Despliegue) y desplegar F1-F4. Mientras no haya acceso: atender los huecos de recuperación (§4) o la opción C del mapa curricular (§F2), si el equipo la aprueba.

## 6. Bitácora

| Fecha | Cambio |
| :--- | :--- |
| 2026-11-10 | Diagnóstico inicial y plan redactado. Decisiones D1-D7 tomadas con el equipo. |
| 2026-11-10 | F1 terminada: tablas `conversaciones` y `mensajes` (cifradas), endpoints `/api/conversaciones`, `/api/chat` con `conversation_id`, barra lateral desde la API (abrir, borrar, conversación activa). El historial no consume cuota. 12 pruebas nuevas (62 en total). Verificado en navegador con dobles del LLM. |
| 2026-11-10 | F1 revisada y aprobada por el usuario en local. F2 terminada: últimos 3 pares (~1,500 tokens) en los `messages`, reescritura con 4o-mini solo con historial (búsqueda con la reescrita, LLM con la original), tokens de reescritura en columnas propias, telemetría en el chat. `tests/conftest.py` fija `RATE_LIMIT_ENABLED=true` para que las pruebas no dependan del `.env` local. 16 pruebas nuevas (78 en total). Verificado con OpenAI real y en navegador. |
| 2026-11-10 | Ajuste de F2 por una alucinación en una primera consulta: filtro de fragmentos casi duplicados en la búsqueda (A) y regla de semestres explícitos en el prompt (B). La opción C (retirar el mapa curricular revuelto del acervo) queda para el equipo. 3 pruebas nuevas (81 en total). |
| 2026-11-10 | F3 implementada: modelos verificados en la documentación y con llamadas reales; tabla `MODELOS`; selector en el chat; cuotas por modelo desde `mensajes` (429 con modelo y hora de liberación); costos con la tarifa de cada modelo. Comparación de 20 preguntas: gpt-6-luna gana (17/20 como los demás, 0.00026 USD por consulta). Se detectó que una respuesta validada en F2 («seiscientas horas» de servicio social) era una alucinación: el reglamento dice 480; las tres corridas actuales responden 480. 16 pruebas nuevas (97 en total). |
| 2026-11-10 | gpt-5.6-luna retirado con la confirmación del usuario (tabla, `.env.example`, `/api/health`, telemetría y panel admin). F3 terminada. 98 pruebas. |
| 2026-11-10 | Revisión del usuario: tablas Markdown en el chat, salida del avanzado a 6,000 tokens (5 veces el rápido) con estilo completo. Se detectó que 26 de 29 enlaces del acervo en el Documento Maestro no abren; la forma de hacer consultables las citas queda pendiente de decisión. 100 pruebas. |
| 2026-11-10 | Citas consultables: catálogo del acervo, enlaces firmados al PDF original en la página citada y visor de texto para las fuentes piloto. Falta subir `data/acervo_original` a la EC2. 113 pruebas. |
| 2026-11-10 | F4 terminada: tablero de usuario y panel admin calculados desde `mensajes` (sin datos de demostración), tokens de embedding persistidos, preguntas sin resultado agrupadas y anónimas, enlace del tablero a la conversación. La etapa 2 de AWS queda con F5. 127 pruebas. |
