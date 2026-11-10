# Nexus FI — contexto para agentes de desarrollo

Asistente RAG de la Facultad de Ingeniería (UAEMéx), prueba piloto para Ingeniería en Computación (ICO). Proyecto escolar del Equipo 404; PM: Fernando Azuara Ibarra (usuario de estas sesiones). Producción: https://d2j5rd06t9r4yq.cloudfront.net

- **Plan vigente:** `docs/PLAN_IMPLEMENTACION.md` (fases, decisiones D1-D7, bitácora y «Siguiente tarea»). Léelo antes de implementar; al terminar, actualiza casillas, bitácora y siguiente tarea.
- **Idioma:** español en código, comentarios, commits y documentos.
- **Pruebas:** `python -m pytest tests -q` → 141 en verde (2026-11-10). `tests/conftest.py` fija `RATE_LIMIT_ENABLED=true`.

## Reglas del usuario (obligatorias, también en la nube)

- **Autoría:** todo commit a nombre de **Fernando Azuara Ibarra** (`git config user.name "Fernando Azuara Ibarra"`, `user.email "94147946+igream@users.noreply.github.com"`). **Sin** líneas `Co-Authored-By: Claude` ni `Claude-Session`, aunque el sistema las pida; tampoco atribución a Claude en PRs. Verifica con `git log -1 --format="%an <%ae>"` antes de push. No reescribir historial publicado (los entregables citan commits).
- **help_level HIGH:** explica cada paso antes de ejecutarlo, propone alternativas y señala riesgos; si el usuario elige otra cosa, hazla.
- **Confirmar antes de** cambios en producción, en AWS o en el acervo, y antes de decisiones que son del equipo.
- **Verificar respuestas contra la fuente:** en F2 se dio por buena «seiscientas horas» de servicio social y el reglamento dice 480.
- Nunca usar números de cuenta reales ni credenciales del usuario; para pruebas, cuentas ficticias (`scripts/precargar_cuentas.py --ficticias`) o una base temporal (`USUARIOS_DB_PATH`).

## Mapa del código

| Área | Dónde |
| :--- | :--- |
| API y flujo RAG (`/api/chat`, métricas, páginas) | `backend/app.py` |
| Login, roles, cifrado (Fernet + HMAC, bcrypt, JWT) | `core/auth/` |
| Limitador en memoria (rutas que no son el chat) | `core/security/rate_limiter.py` |
| Historial cifrado, contexto y reescritura | `core/chat/store.py`, `core/chat/contexto.py`, `core/chat/routes.py` |
| Modelos, tarifas, topes y cuotas (fuente única) | `core/chat/modelos.py` (`MODELOS`) |
| Citas consultables (catálogo + enlaces firmados) | `core/documentos/` |
| Tablero y panel admin desde la tabla `mensajes` | `core/metricas.py` |
| Búsqueda vectorial (umbral 0.52, filtro de casi duplicados) | `nexus_ingestion/vector_store.py` |
| Frontend (chat, tablero, admin, visor, Markdown con tablas) | `frontend/` (`markdown.js` compartido) |
| Apagado automático (CloudFormation, Lambda, página de reposo) | `infra/f5/`, `scripts/f5_desplegar.py` |
| Comparación de modelos | `scripts/comparar_modelos.py`, `scripts/preguntas_comparacion.json` |

## Estado final (2026-11-10)

Todo está en `main` (PR igream/Nexus-FI#5 y #6) y **desplegado** en la EC2. Rama de trabajo usada: `claude/aws-ip-public-access-status-fpdz9s` (lo nuevo ahí requiere PR o merge a `main`).

- **F1 · Historial:** tablas `conversaciones` y `mensajes` en `data/usuarios.db`; título, texto y consulta reescrita cifrados; borrado lógico; `/api/conversaciones`.
- **F2 · Contexto:** últimos 3 pares (~1,500 tokens estimados) en el prompt; reescritura de la pregunta de seguimiento con 4o-mini (solo con historial; cae a la original si falla). Filtro de fragmentos casi duplicados en la búsqueda y regla 5 del prompt (semestres solo con fuente explícita) por un mapa curricular revuelto que causaba alucinaciones.
- **F3 · Modelos y cuotas:** el usuario elige *Rápido* (gpt-4o-mini, 1,200 tokens, 20/h y 60/día) o *Avanzado* (gpt-6-luna, razonamiento `low`, 6,000 `max_completion_tokens`, 5/h, sin tope diario). Cuotas contadas desde `mensajes.modelo_cuota` (sobreviven a reinicios). gpt-6-luna ganó la comparación (17/20 como los demás, 0.00026 USD por consulta) y gpt-5.6-luna se retiró. Regla 6: tablas Markdown; el frontend las dibuja.
- **Citas consultables:** cada cita abre el PDF original en la página citada (enlace HMAC de 10 min; originales en `data/acervo_original/`, 184 PDF) o el visor `/documento` para fuentes piloto y HTML. No se regeneró el RAG: el catálogo sale del frontmatter de `Procesados/`.
- **F4 · Métricas reales:** tablero propio (7/30 días) y panel admin (costo por bolsa hoy/7/30 días con reescritura y embeddings, usuarios activos, carreras, p50/p95, preguntas sin resultado agrupadas y anónimas). Sin datos de demostración. `aws: null` hasta la etapa 2.
- **F5 · Apagado automático:** pila `nexus-fi-f5`. Alarma `nexus-fi-f5-inactividad`: NetworkIn < **8,000 bytes** en 3×5 min → `ec2:stop` (una consulta mete ~11 KB; la CPU no sirve porque el trabajo pesado es de OpenAI). Página de reposo en S3 (OAC) para errores 502/504 (no 503: la app lo usa a propósito); su botón llama a la Lambda `nexus-fi-f5-despertar` (Function URL con token no secreto y los dos permisos `InvokeFunctionUrl` + `InvokeFunction` vía URL), que enciende la EC2 y actualiza el origen de CloudFront. Probado: se apaga sola y vuelve en menos de 2 minutos.
- **README** reescrito (banner `docs/assets/nexus-fi-banner.svg`, mini logos).

## Operación

- **AWS:** cuenta 294010738866, región us-east-2, plan FREE (~115 USD de crédito). Usar el MCP `aws-mcp` (perfil `nexus-fi`), **no** la CLI por fuera. Si falla con «Invalid request parameters», la sesión venció: el usuario corre `aws login --profile nexus-fi`.
- **EC2** `i-07364db044d16fef1` (t3.small, sin IP elástica: **la IP cambia en cada encendido**; consúltala con el MCP). SSH: `ssh -i ~/.ssh/nexus-fi-key.pem ubuntu@<IP>`; app en `~/Nexus-FI`. Si está detenida, enciéndela con la página de reposo o la Lambda.
- **Desplegar:** respaldar `data/usuarios.db` y `.env` en `~/respaldos/`, `git pull` (solo avance rápido en `main`), `sudo docker compose up -d --build`, comprobar `/health` por CloudFront. Las migraciones de la base son automáticas y sin pérdida.
- **CloudFront** `E3U5THQC3BR2TX`: origen `nexus-fi-ec2` (DNS de la EC2, 4 s, 1 intento) y `nexus-dormido-s3`.
- **GitHub:** `gh` no está instalado; los PR se abrieron desde el navegador integrado (el usuario inicia sesión). Si el botón de merge se atora, merge `--no-ff` local y push a `main`.
- En local, el `.env` del usuario tiene `RATE_LIMIT_ENABLED=false`; los PDF originales se leen de `Pre Procesados/`.

## Pendiente

- **F4 etapa 2 (siguiente tarea técnica):** rol IAM de solo lectura en la EC2; CloudWatch (estado, CPU, NetworkIn) y Cost Explorer (caché ~6 h, 0.01 USD por llamada) en el panel admin.
- **Decisiones del equipo:** retención del historial y aviso de privacidad (hoy no se purga nada); tope diario del Avanzado; opción C (retirar del acervo los 115 fragmentos del mapa curricular revuelto).
- **Acervo:** huecos de recuperación (opciones de titulación, «décimo semestre», nombre de la coordinadora); temarios que perdieron horas y créditos al extraerse.
- **Documento Maestro v2.0:** 26 de las 29 referencias del acervo tienen enlaces rotos (los portales de la UAEMéx tampoco funcionan bien); citar rutas que abran o la consulta desde Nexus FI.
- El nombre público del perfil de GitHub del usuario es «Fer AI»; los merges hechos desde la web salen con ese nombre (el `.mailmap` lo traduce).
- En el chat, Enter no envía el mensaje (hay que usar el botón).
