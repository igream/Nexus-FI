# Imagen base oficial de Python
FROM python:3.11-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Mostrar los mensajes de Python en `docker compose logs` al momento
ENV PYTHONUNBUFFERED=1

# Copiar archivos de requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Puerto donde corre el backend (FastAPI / Uvicorn)
EXPOSE 8000

# Comando para iniciar la aplicación
# backend.app:app es la aplicación FastAPI real (RAG + middlewares WBS 1.3.5 / 1.4.2)
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
