# Plan de implementación — Nexus FI (post-piloto)

Documento de trabajo para las sesiones de desarrollo con Claude Code. Antes de empezar una tarea:
1. Lee este archivo completo.
2. Revisa **Siguiente tarea** y la **Bitácora**.
3. Al terminar, marca las casillas, actualiza la bitácora y la siguiente tarea, y haz commit de este archivo con el código.

Última actualización: 2026-11-10.

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

### F2. Contexto conversacional

**Tareas:**
- [ ] Al responder, incluir los últimos N turnos de la conversación (propuesta: 3 pares de pregunta y respuesta, recortados a unos 1,500 tokens) entre el prompt de sistema y la pregunta actual.
- [ ] **Reescritura de la pregunta:** solo si hay historial, hacer una llamada a `gpt-4o-mini` (temperature 0, máximo unos 100 tokens) que convierta la pregunta de seguimiento en una pregunta autónoma.
  - El embedding y la búsqueda en LanceDB usan la versión reescrita; al LLM final se le pasan el historial y la pregunta original.
  - Guardar la reescritura en `mensajes.consulta_reescrita`.
  - Si la reescritura falla, usar la pregunta original.
- [ ] Contar los tokens de la reescritura en la bolsa de 4o-mini.
- [ ] Mostrar la reescritura en la telemetría.

**Pruebas:**
- [ ] Sin historial no hay llamada de reescritura.
- [ ] Con historial, los `messages` enviados al LLM incluyen los turnos previos en orden y respetan el límite N.
- [ ] Prueba manual: preguntar "¿Qué requisitos tiene el servicio social?" y luego "¿y cuál es el plazo?". La segunda debe recuperar fuentes de servicio social.
- [ ] Una falla en la reescritura no rompe la respuesta.

### F3. Selector de modelo y cuotas por modelo

**Antes de programar**, verificar en la documentación de OpenAI (desde esta sesión `developers.openai.com` estaba bloqueado por la red):
- [ ] Identificadores exactos, precio de entrada, entrada en caché y salida, y endpoint soportado (Chat Completions o Responses).
- [ ] Parámetros que no se admiten. Los modelos de razonamiento suelen exigir `max_completion_tokens` en vez de `max_tokens`, no aceptan `temperature` y usan `reasoning_effort`.

**Comparación gpt-6-luna vs gpt-5.6-luna:**
- [ ] Script `scripts/comparar_modelos.py`:
  - Unas 20 preguntas reales del acervo, con respuesta esperada y fuente.
  - Medir aciertos, citas correctas, latencia, tokens y costo por consulta.
  - Guardar el resultado en `docs/02_Ejecucion/`.
- [ ] Elegir el ganador y retirar el otro de la configuración (variable de entorno, cliente y bolsa del panel).

**Tareas:**
- [ ] Corregir `backend/app.py:554`: llamar al modelo elegido, no al fijo.
- [ ] Tabla única de modelos (`MODELOS = {...}`) con: id de API, clave, tarifas, tope de salida, cuota por hora y por día, y parámetros admitidos.
- [ ] Validar `model` contra esa tabla y responder 422 si no existe.
- [ ] **Cuotas por modelo:**
  - Mover la verificación al endpoint, o leer `model` del cuerpo en el middleware.
  - Contar desde la tabla `mensajes` (`usuario_id`, `modelo`, `creado_en`) para que las cuotas sobrevivan a los reinicios.
  - El 429 debe indicar qué modelo se agotó y cuándo se libera.
- [ ] Tope de salida por modelo (propuesta: 4o-mini 1,200 tokens; avanzado entre 1,500 y 2,000, definir con la comparación).
- [ ] `/api/session/info` devuelve la cuota restante de cada modelo.
- [ ] Frontend:
  - Selector "Rápido (4o-mini)" o "Avanzado (gpt-6)" junto al cuadro de texto, que recuerda la última elección.
  - Mostrar la cuota restante del modelo elegido.
  - Desactivar "Avanzado" si su cuota se agotó.

**Pruebas:**
- [ ] El modelo enviado a la API es el elegido (cliente simulado).
- [ ] Un modelo inválido da 422.
- [ ] Al agotar el avanzado (5 por hora) llega un 429 para él mientras 4o-mini sigue disponible, y viceversa.
- [ ] Las cuotas se conservan tras reabrir la base.
- [ ] El costo registrado usa la tarifa del modelo correcto.
- [ ] Actualizar `tests/test_rate_limiter.py` si cambia la interfaz.

### F4. Tablero de usuario y panel admin reales

**Tablero de usuario** (`/api/v1/metrics/user-dashboard`, con sesión y solo datos propios):
- [ ] Consultas totales y por modelo, por día de los últimos 7 y 30.
- [ ] Cuota restante por modelo.
- [ ] Temas frecuentes (`categoria_principal`).
- [ ] Latencia promedio.
- [ ] Últimas conversaciones con enlace.

**Panel admin** (`/api/v1/admin/metrics`, solo administradores):
- [ ] Tokens y costo por modelo, por día, semana y mes, calculados desde `mensajes` más los embeddings.
- [ ] Usuarios activos y consultas por carrera.
- [ ] Consultas sin resultado (`encontrado = 0`), útiles para ampliar el acervo.
- [ ] Latencia p50 y p95.
- [ ] Sección AWS: quitar los valores fijos. En una segunda etapa, datos reales con CloudWatch (CPU y estado de la instancia) y Cost Explorer (0.01 USD por llamada; guardar en caché unas 6 horas). Antes hay que darle a la instancia un rol IAM.
- [ ] Eliminar `user_metrics_store`, `admin_tokens_store` y los textos `baseline_demo`.

**Pruebas:**
- [ ] El tablero exige sesión.
- [ ] Dos usuarios ven datos distintos.
- [ ] Un usuario sin rol de admin recibe 403 en el panel.
- [ ] Los totales coinciden con los mensajes sembrados en la prueba.

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

- [ ] Identificadores, precios y parámetros de gpt-6-luna y gpt-5.6-luna. Hay que permitir `developers.openai.com` en la red de la sesión, o pegar los datos aquí.
- [ ] Acceso a AWS desde la sesión: el conector de AWS necesita volver a autenticarse en la configuración de conectores de claude.ai, o hay que darle a la sesión una clave IAM.
- [ ] Tope diario del modelo avanzado.
- [ ] Retención del historial y texto del aviso de privacidad.

## 5. Siguiente tarea

**F2: contexto conversacional.** Usar `chat_store.obtener_conversacion` (o una consulta nueva que traiga solo los últimos N mensajes) para armar los turnos previos en `/api/chat`. Después, la reescritura de la pregunta con 4o-mini, guardada en `consulta_reescrita` (el parámetro ya existe en `agregar_mensaje`). Las pruebas de `tests/test_conversaciones.py` ya tienen dobles del LLM y del buscador que registran las llamadas (`client.llm.llamadas`).

## 6. Bitácora

| Fecha | Cambio |
| :--- | :--- |
| 2026-11-10 | Diagnóstico inicial y plan redactado. Decisiones D1-D7 tomadas con el equipo. |
| 2026-11-10 | F1 terminada: tablas `conversaciones` y `mensajes` (cifradas), endpoints `/api/conversaciones`, `/api/chat` con `conversation_id`, barra lateral desde la API (abrir, borrar, conversación activa). El historial no consume cuota. 12 pruebas nuevas (62 en total). Verificado en navegador con dobles del LLM. |
