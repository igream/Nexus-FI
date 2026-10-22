import os
import time
from dotenv import load_dotenv
import openai
import boto3

# Cargar variables del archivo .env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

print("--- Módulo DT-10: Seguridad y Telemetría ---")
print(f"API Key OpenAI configurada: {'Sí' if OPENAI_API_KEY else 'No'}")
print(f"AWS Access Key configurada: {'Sí' if AWS_ACCESS_KEY_ID else 'No'}")

# Inicializar cliente de OpenAI
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Lógica básica de llamada y telemetría
def enviar_consulta(prompt):
    inicio = time.time()
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    
    fin = time.time()
    tiempo_respuesta = round(fin - inicio, 2)
    
    contenido = response.choices[0].message.content
    print(f"\n[Telemetría] Tiempo de respuesta: {tiempo_respuesta}s")
    print(f"[Respuesta OpenAI]: {contenido}")

if __name__ == "__main__":
    enviar_consulta("Hola, este es un mensaje de prueba para la telemetría.")