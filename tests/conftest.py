"""
Configuración común de las pruebas.

El límite de consultas se activa siempre, sin importar el `.env` local: en desarrollo
suele estar en RATE_LIMIT_ENABLED=false y las pruebas de cuota darían falsos fallos.
Debe fijarse antes de importar backend.app, porque ahí se decide si se monta el
middleware; load_dotenv no sobrescribe variables ya definidas.
"""
import os

os.environ["RATE_LIMIT_ENABLED"] = "true"
