# Carpeta de Configuración y Procedimientos de la API de Gemini
## NexusFI UAEMéx — Asistente de Ingeniería en Computación

Esta carpeta encapsula toda la documentación, scripts de diagnóstico, plantillas y protocolos de ciberseguridad necesarios para gestionar de forma óptima la **API Key de Google Gemini**.

---

##  Contenido del Módulo `Confg API`

| Archivo | Tipo | Descripción |
| :--- | :--- | :--- |
| **`Guia_Gestion_Segura_APIKEY_Gemini.docx`** | Documento Word | Manual formal ejecutivo con tablas, formato institucional y matriz de seguridad. |
| **`probar_conexion_api.py`** | Script Python | Herramienta de diagnóstico que verifica cuotas, latencia y respuesta con Auto-Fallback. |
| **`auditor_seguridad_api.py`** | Script Python | Escáner de seguridad que audita que tu `.env` esté protegido y no haya fugas en Git. |
| **`generar_vectores_api.py`** | Script Python | Utilidad para calcular embeddings vectoriales (`gemini-embedding-2`) de tus textos. |
| **`ejecutar_diagnostico.bat`** | Script Windows | Ejecutable en 1 clic para correr el test de conexión y auditoría en consola. |
| **`.env.plantilla`** | Archivo de Texto | Plantilla pública limpia para inicializar variables sin secretos expuestos. |
| **`modelos_soportados.json`** | Archivo JSON | Catálogo técnico de modelos activos de chat y embeddings de Google AI Studio. |

---

##  PROCEDIMIENTO 1: Cómo Obtener tu API Key Gratuita de Gemini

1. **Ingreso a la plataforma:**
   - Abre tu navegador y dirígete a: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. **Inicio de sesión:**
   - Inicia sesión con cualquier cuenta de Google (personal `@gmail.com` o correo institucional `@alumno.uaemex.mx`).
3. **Creación de la llave:**
   - Haz clic en el botón azul **"+ Create API key"**.
   - Selecciona **"Create API key in new project"** (esto aísla métricas y cuotas).
4. **Copia de seguridad:**
   - Haz clic en el botón **"Copy"** para copiar la cadena secreta (comienza típicamente con `AIzaSy...` o `AQ...`).
   - *Nota:* El plan gratuito no requiere ingresar tarjeta de crédito.

---

##  PROCEDIMIENTO 2: Cómo Configurar la API Key en el Chatbot

Tienes dos métodos disponibles:

### Método A: Desde la Interfaz Web (Recomendado)
1. Ejecuta el archivo `run.bat` del proyecto para abrir el navegador en `http://127.0.0.1:8000`.
2. En la barra lateral izquierda, haz clic en el botón **"Ajustes / API Key"**.
3. Pega tu clave en el campo correspondiente y presiona **"Guardar y Probar"**.
4. La aplicación validará la autenticidad con Google y la guardará automáticamente en el archivo `.env` del proyecto.

### Método B: Mediante Archivo `.env` Manual
1. Abre el archivo `.env` en la raíz del proyecto (o copia `.env.plantilla` como `.env`).
2. Escribe tu clave:
   ```env
   GEMINI_API_KEY=tu_clave_secreta_aqui
   GEMINI_MODEL=gemini-3.8-flash
   ```
3. Guarda el archivo y reinicia el servidor.

---

##  PROCEDIMIENTO 3: Protocolo para Subir el Proyecto a GitHub de Forma Segura

Para publicar tu código en GitHub, GitLab o Bitbucket sin exponer tus credenciales a robos o bots maliciosos:

### Paso 1: Verificar el archivo `.gitignore`
Asegúrate de que el archivo `.gitignore` contenga la regla para bloquear `.env`:
```gitignore
# Variables de entorno y secretos
.env
.env.local
*.key
*.pem
```

### Paso 2: Ejecutar el Auditor de Seguridad
Antes de hacer commit, corre el script auditor que creamos en esta carpeta:
```powershell
python "Confg API\auditor_seguridad_api.py"
```
El auditor confirmará que tu clave no se encuentra en el código ni lista para subirse.

### Paso 3: Checklist en Terminal antes de `git push`
1. Revisa qué archivos se van a subir:
   ```bash
   git status
   ```
   *(Verifica visualmente que `.env` NO aparezca en verde ni en rojo).*
2. Sube únicamente la plantilla `.env.plantilla` o `.env.example`:
   ```bash
   git add .
   git commit -m "feat: implementacion chatbot RAG uaemex"
   git push origin main
   ```

---

## PROCEDIMIENTO 4: Despliegue Seguro en Producción (Cloud / Servidores)

Cuando alojes tu chatbot en un servidor en la nube (Render, Railway, Vercel, Docker o AWS):
- **NUNCA subas el archivo `.env` al servidor.**
- Ve a la sección **"Environment Variables"** en el panel de control de tu proveedor.
- Añade una variable con el nombre **`GEMINI_API_KEY`** y como valor pega tu API Key secreta.
- El servidor la inyectará de forma cifrada en la memoria RAM del proceso sin dejar rastro en disco.

---

## PROCEDIMIENTO 5: Qué Hacer si tu API Key se Filtra por Accidente

Si por descuido subiste tu archivo `.env` a un repositorio público:
1. **Revocación inmediata en 10 segundos:**
   - Entra a [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Busca la clave comprometida y haz clic en el icono del bote de basura (**"Delete API Key"**).
   - A partir de ese segundo, la clave quedará desactivada en todo el mundo y nadie podrá usar tus cuotas.
2. **Generación de nueva clave:**
   - Haz clic en **"Create API key"** para generar una clave nueva.
3. **Actualización local:**
   - Actualiza tu archivo `.env` local con la nueva clave.
