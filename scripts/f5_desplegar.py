"""
F5 - apagado automático de la EC2 de Nexus FI (plan de implementación, §F5).

  python scripts/f5_desplegar.py calibrar  [--horas 24]
      Estadísticas de NetworkIn (suma por 5 min) y CPU (promedio) de la instancia para elegir
      el umbral de la alarma: compara las horas sin uso con las horas de clase.

  python scripts/f5_desplegar.py desplegar [--metrica NetworkIn] [--umbral 8000]
      1. Crea o actualiza la pila infra/f5/apagado.yaml (alarma, Lambda, Function URL, bucket, OAC).
      2. Sube la página infra/f5/dormido/index.html al bucket con la URL y el token.
      3. Ajusta la distribución de CloudFront: origen S3 con OAC, ruta /dormido/*, errores
         502/504 -> página dormido (503 no: la app lo usa a propósito) y conexión al origen
         EC2 de 4 s con un intento, para mostrar la página rápido.

Requiere credenciales de AWS con permisos sobre CloudFormation, EC2, CloudWatch, Lambda, IAM,
S3 y CloudFront. Región de la instancia: us-east-2 (los recursos de CloudFront son globales).
"""
import argparse
import copy
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "infra" / "f5" / "apagado.yaml"
CODIGO = RAIZ / "infra" / "f5" / "despertar.py"
PAGINA = RAIZ / "infra" / "f5" / "dormido" / "index.html"

INSTANCIA = "i-07364db044d16fef1"
DISTRIBUCION = "E3U5THQC3BR2TX"
REGION = "us-east-2"
PILA = "nexus-fi-f5"
ORIGEN_S3 = "nexus-dormido-s3"
RUTA_PAGINA = "/dormido/index.html"
ERRORES_DORMIDO = (502, 504)
CACHE_DESACTIVADA = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"   # política administrada CachingDisabled


# ---------------------------------------------------------------------------
# Funciones puras (probadas en tests/test_f5.py)
# ---------------------------------------------------------------------------
def plantilla_con_codigo(plantilla: str, codigo: str) -> str:
    """Inserta el código de la Lambda en el bloque ZipFile, con la sangría del marcador."""
    for linea in plantilla.splitlines():
        if linea.strip() == "__CODIGO_DESPERTAR__":
            sangria = linea[: len(linea) - len(linea.lstrip())]
            bloque = "\n".join((sangria + l) if l.strip() else "" for l in codigo.rstrip().splitlines())
            return plantilla.replace(linea, bloque, 1)
    raise ValueError("La plantilla no tiene el marcador __CODIGO_DESPERTAR__")


def pagina_dormido(html: str, url_despertar: str, token: str) -> str:
    if "__URL_DESPERTAR__" not in html or "__TOKEN_DESPERTAR__" not in html:
        raise ValueError("La página no tiene los marcadores esperados")
    return html.replace("__URL_DESPERTAR__", url_despertar.rstrip("/")).replace("__TOKEN_DESPERTAR__", token)


def origen_ec2(cfg: dict) -> dict:
    """El origen de la distribución que apunta al DNS público de la EC2."""
    candidatos = [o for o in cfg["Origins"]["Items"] if o["DomainName"].endswith(".compute.amazonaws.com")]
    if len(candidatos) != 1:
        raise ValueError(f"Se esperaba un origen EC2 y hay {len(candidatos)}")
    return candidatos[0]


def ajustar_distribucion(cfg: dict, dominio_bucket: str, oac_id: str) -> dict:
    """Configuración nueva de la distribución con la página dormido. Es idempotente."""
    cfg = copy.deepcopy(cfg)
    ec2 = origen_ec2(cfg)
    ec2["ConnectionAttempts"] = 1
    ec2["ConnectionTimeout"] = 4

    origenes = [o for o in cfg["Origins"]["Items"] if o["Id"] != ORIGEN_S3]
    origenes.append({
        "Id": ORIGEN_S3, "DomainName": dominio_bucket, "OriginPath": "",
        "CustomHeaders": {"Quantity": 0}, "S3OriginConfig": {"OriginAccessIdentity": ""},
        "OriginAccessControlId": oac_id, "ConnectionAttempts": 3, "ConnectionTimeout": 10,
        "OriginShield": {"Enabled": False},
    })
    cfg["Origins"] = {"Quantity": len(origenes), "Items": origenes}

    comportamientos = [c for c in cfg.get("CacheBehaviors", {}).get("Items", []) if c["PathPattern"] != "/dormido/*"]
    comportamientos.append({
        "PathPattern": "/dormido/*", "TargetOriginId": ORIGEN_S3, "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"],
                           "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
        "Compress": True, "CachePolicyId": CACHE_DESACTIVADA, "SmoothStreaming": False,
        "FieldLevelEncryptionId": "", "LambdaFunctionAssociations": {"Quantity": 0},
        "FunctionAssociations": {"Quantity": 0},
        "TrustedSigners": {"Enabled": False, "Quantity": 0}, "TrustedKeyGroups": {"Enabled": False, "Quantity": 0},
    })
    cfg["CacheBehaviors"] = {"Quantity": len(comportamientos), "Items": comportamientos}

    errores = [e for e in cfg.get("CustomErrorResponses", {}).get("Items", []) if e["ErrorCode"] not in ERRORES_DORMIDO]
    errores += [{"ErrorCode": c, "ResponsePagePath": RUTA_PAGINA, "ResponseCode": "503", "ErrorCachingMinTTL": 0}
                for c in ERRORES_DORMIDO]
    cfg["CustomErrorResponses"] = {"Quantity": len(errores), "Items": errores}
    return cfg


def resumen_calibracion(puntos: list[float]) -> dict:
    v = sorted(puntos)
    if not v:
        return {"muestras": 0}
    pick = lambda p: v[min(len(v) - 1, int(p / 100 * len(v)))]
    return {"muestras": len(v), "min": v[0], "p10": pick(10), "p50": pick(50), "p90": pick(90), "max": v[-1]}


# ---------------------------------------------------------------------------
# Llamadas a AWS
# ---------------------------------------------------------------------------
def calibrar(horas: int) -> None:
    import boto3
    cw = boto3.client("cloudwatch", region_name=REGION)
    fin = datetime.now(timezone.utc)
    for metrica, estad in (("NetworkIn", "Sum"), ("CPUUtilization", "Average")):
        r = cw.get_metric_statistics(Namespace="AWS/EC2", MetricName=metrica, StartTime=fin - timedelta(hours=horas),
                                     EndTime=fin, Period=300, Statistics=[estad],
                                     Dimensions=[{"Name": "InstanceId", "Value": INSTANCIA}])
        print(metrica, estad, resumen_calibracion([p[estad] for p in r["Datapoints"]]))


def desplegar(metrica: str, umbral: float) -> None:
    import boto3
    cfn = boto3.client("cloudformation", region_name=REGION)
    cf = boto3.client("cloudfront")
    s3 = boto3.client("s3", region_name=REGION)

    actual = cf.get_distribution_config(Id=DISTRIBUCION)
    dominio = cf.get_distribution(Id=DISTRIBUCION)["Distribution"]["DomainName"]
    token = secrets.token_urlsafe(24)
    parametros = {"InstanciaId": INSTANCIA, "DistribucionId": DISTRIBUCION, "DominioCloudFront": dominio,
                  "OrigenEc2Id": origen_ec2(actual["DistributionConfig"])["Id"], "TokenDespertar": token,
                  "MetricaInactividad": metrica, "UmbralInactividad": str(umbral)}
    cuerpo = plantilla_con_codigo(PLANTILLA.read_text(encoding="utf-8"), CODIGO.read_text(encoding="utf-8"))
    args = dict(StackName=PILA, TemplateBody=cuerpo, Capabilities=["CAPABILITY_IAM"],
                Parameters=[{"ParameterKey": k, "ParameterValue": v} for k, v in parametros.items()])
    try:
        cfn.describe_stacks(StackName=PILA)
        cfn.update_stack(**args)
        espera = "stack_update_complete"
    except cfn.exceptions.ClientError as e:
        if "does not exist" not in str(e):
            raise
        cfn.create_stack(**args)
        espera = "stack_create_complete"
    print("Esperando la pila…")
    cfn.get_waiter(espera).wait(StackName=PILA)
    salidas = {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=PILA)["Stacks"][0]["Outputs"]}

    html = pagina_dormido(PAGINA.read_text(encoding="utf-8"), salidas["UrlDespertar"], token)
    s3.put_object(Bucket=salidas["BucketDormido"], Key=RUTA_PAGINA.lstrip("/"), Body=html.encode("utf-8"),
                  ContentType="text/html; charset=utf-8", CacheControl="no-store")

    actual = cf.get_distribution_config(Id=DISTRIBUCION)
    nueva = ajustar_distribucion(actual["DistributionConfig"], salidas["DominioBucketDormido"], salidas["OacDormidoId"])
    cf.update_distribution(Id=DISTRIBUCION, IfMatch=actual["ETag"], DistributionConfig=nueva)
    print("Listo. La distribución tarda unos minutos en propagarse.")
    print("Function URL:", salidas["UrlDespertar"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    c = sub.add_parser("calibrar")
    c.add_argument("--horas", type=int, default=24)
    d = sub.add_parser("desplegar")
    d.add_argument("--metrica", choices=["NetworkIn", "CPUUtilization"], default="NetworkIn")
    d.add_argument("--umbral", type=float, default=8000)
    a = ap.parse_args()
    calibrar(a.horas) if a.accion == "calibrar" else desplegar(a.metrica, a.umbral)


if __name__ == "__main__":
    sys.exit(main())
