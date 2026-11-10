"""Lambda nexus-despertar (F5): enciende la EC2 de Nexus FI y apunta CloudFront a su DNS nuevo.

La página «servidor dormido» la llama cada pocos segundos; cada llamada es idempotente:
  detenida -> StartInstances | pending/stopping -> esperar | running -> origen = DNS actual
Token simple en la cabecera x-nexus-token: viaja en una página pública, así que solo frena
a escáneres; lo peor que permite es encender la instancia.
"""
import hmac
import json
import os

import boto3

_ec2 = None
_cf = None


def _clientes():
    global _ec2, _cf
    if _ec2 is None:
        _ec2 = boto3.client("ec2")
        _cf = boto3.client("cloudfront")
    return _ec2, _cf


def _resp(codigo, cuerpo):
    return {"statusCode": codigo, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(cuerpo, ensure_ascii=False)}


def handler(event, context):
    cabeceras = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if not hmac.compare_digest(cabeceras.get("x-nexus-token", ""), os.environ["TOKEN"]):
        return _resp(403, {"error": "token no valido"})
    ec2, cf = _clientes()
    iid = os.environ["INSTANCE_ID"]
    inst = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
    estado = inst["State"]["Name"]
    if estado == "stopped":
        ec2.start_instances(InstanceIds=[iid])
        return _resp(202, {"estado": "arrancando"})
    if estado != "running":
        return _resp(202, {"estado": estado})
    dns = inst.get("PublicDnsName")
    if not dns:
        return _resp(202, {"estado": "sin_dns"})
    dist = os.environ["DISTRIBUTION_ID"]
    r = cf.get_distribution_config(Id=dist)
    cfg = r["DistributionConfig"]
    origen = next(o for o in cfg["Origins"]["Items"] if o["Id"] == os.environ["ORIGIN_ID"])
    if origen["DomainName"] == dns:
        return _resp(200, {"estado": "listo"})
    origen["DomainName"] = dns
    cf.update_distribution(Id=dist, IfMatch=r["ETag"], DistributionConfig=cfg)
    return _resp(200, {"estado": "actualizando_origen"})
