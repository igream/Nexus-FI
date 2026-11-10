"""
Pruebas sin red de F5 (apagado automático): la Lambda nexus-despertar con clientes simulados,
la plantilla de CloudFormation y los ajustes de la distribución de CloudFront.
"""
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from scripts import f5_desplegar as f5

RAIZ = Path(__file__).resolve().parent.parent
TOKEN = "token-de-prueba-0123456789"


def _cargar_lambda():
    spec = importlib.util.spec_from_file_location("despertar", RAIZ / "infra" / "f5" / "despertar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _EC2:
    def __init__(self, estado, dns=""):
        self.estado, self.dns, self.arrancadas = estado, dns, []

    def describe_instances(self, InstanceIds):
        return {"Reservations": [{"Instances": [{"State": {"Name": self.estado}, "PublicDnsName": self.dns}]}]}

    def start_instances(self, InstanceIds):
        self.arrancadas.append(InstanceIds)


class _CF:
    def __init__(self, dominio):
        self.cfg = {"Origins": {"Quantity": 1, "Items": [{"Id": "ec2", "DomainName": dominio}]}}
        self.actualizaciones = []

    def get_distribution_config(self, Id):
        return {"ETag": "E1", "DistributionConfig": json.loads(json.dumps(self.cfg))}

    def update_distribution(self, Id, IfMatch, DistributionConfig):
        self.actualizaciones.append((IfMatch, DistributionConfig))


@pytest.fixture
def lam(monkeypatch):
    mod = _cargar_lambda()
    for k, v in {"TOKEN": TOKEN, "INSTANCE_ID": "i-1", "DISTRIBUTION_ID": "D1", "ORIGIN_ID": "ec2"}.items():
        monkeypatch.setenv(k, v)
    return mod


def invocar(mod, ec2, cf, token=TOKEN):
    mod._ec2, mod._cf = ec2, cf
    r = mod.handler({"headers": {"X-Nexus-Token": token}}, None)
    return r["statusCode"], json.loads(r["body"])


# --- Lambda nexus-despertar --------------------------------------------------------

def test_token_invalido_da_403_y_no_toca_nada(lam):
    ec2 = _EC2("stopped")
    assert invocar(lam, ec2, _CF("x"), token="otro")[0] == 403
    assert ec2.arrancadas == []


def test_instancia_detenida_se_enciende(lam):
    ec2 = _EC2("stopped")
    assert invocar(lam, ec2, _CF("x")) == (202, {"estado": "arrancando"})
    assert ec2.arrancadas == [["i-1"]]


@pytest.mark.parametrize("estado", ["pending", "stopping"])
def test_en_transicion_solo_espera(lam, estado):
    ec2 = _EC2(estado)
    assert invocar(lam, ec2, _CF("x")) == (202, {"estado": estado})
    assert ec2.arrancadas == []


def test_encendida_con_el_mismo_dns_esta_lista(lam):
    cf = _CF("ec2-1-2-3-4.us-east-2.compute.amazonaws.com")
    assert invocar(lam, _EC2("running", "ec2-1-2-3-4.us-east-2.compute.amazonaws.com"), cf) == (200, {"estado": "listo"})
    assert cf.actualizaciones == []


def test_dns_nuevo_actualiza_el_origen_de_cloudfront(lam):
    cf = _CF("ec2-viejo.us-east-2.compute.amazonaws.com")
    codigo, cuerpo = invocar(lam, _EC2("running", "ec2-nuevo.us-east-2.compute.amazonaws.com"), cf)
    assert (codigo, cuerpo["estado"]) == (200, "actualizando_origen")
    etag, cfg = cf.actualizaciones[0]
    assert etag == "E1" and cfg["Origins"]["Items"][0]["DomainName"] == "ec2-nuevo.us-east-2.compute.amazonaws.com"


def test_codigo_cabe_inline_en_la_plantilla():
    assert len((RAIZ / "infra" / "f5" / "despertar.py").read_bytes()) < 4096


# --- Plantilla -----------------------------------------------------------------------

class _CargadorCfn(yaml.SafeLoader):
    pass


def _etiqueta_cfn(loader, node):
    """Las funciones intrínsecas (!Ref, !Sub…) se leen como tuplas (etiqueta, valor)."""
    if isinstance(node, yaml.ScalarNode):
        valor = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        valor = loader.construct_sequence(node, deep=True)
    else:
        valor = loader.construct_mapping(node, deep=True)
    return (node.tag, valor)


for _tag in ("!Ref", "!Sub", "!GetAtt", "!If", "!Equals"):
    _CargadorCfn.add_constructor(_tag, _etiqueta_cfn)


@pytest.fixture(scope="module")
def plantilla():
    texto = f5.plantilla_con_codigo(f5.PLANTILLA.read_text(encoding="utf-8"), f5.CODIGO.read_text(encoding="utf-8"))
    return texto, yaml.load(texto, Loader=_CargadorCfn)


def test_plantilla_inserta_el_codigo(plantilla):
    texto, t = plantilla
    codigo = t["Resources"]["FuncionDespertar"]["Properties"]["Code"]["ZipFile"]
    assert "def handler(event, context):" in codigo and "__CODIGO_DESPERTAR__" not in texto
    compile(codigo, "index.py", "exec")   # el código insertado sigue siendo Python válido


def test_alarma_usa_la_accion_nativa_de_apagado(plantilla):
    a = plantilla[1]["Resources"]["AlarmaInactividad"]["Properties"]
    assert a["AlarmActions"] == [("!Sub", "arn:aws:automate:${AWS::Region}:ec2:stop")]
    assert a["TreatMissingData"] == "notBreaching" and a["ComparisonOperator"] == "LessThanThreshold"
    assert a["Period"] == 300 and "Metrics" not in a   # sin metric math: no podría apagar la EC2


def test_seguridad_de_la_plantilla(plantilla):
    texto, t = plantilla
    r = t["Resources"]
    assert all(r["BucketDormido"]["Properties"]["PublicAccessBlockConfiguration"].values())
    assert r["PermisoUrlPublica"]["Properties"]["FunctionUrlAuthType"] == "NONE"
    assert r["FuncionDespertar"]["Properties"]["Environment"]["Variables"]["TOKEN"] == ("!Ref", "TokenDespertar")
    assert t["Parameters"]["TokenDespertar"]["NoEcho"] is True
    acciones = [s["Action"] for p in r["RolDespertar"]["Properties"]["Policies"] for s in p["PolicyDocument"]["Statement"]]
    assert "*" not in json.dumps(acciones) and "0.0.0.0/0" not in texto
    assert t["Metadata"]["AWSToolsMetrics"]["AWSAgentToolkit"] == "aws-cloudformation@3"


# --- Página y distribución -----------------------------------------------------------

def test_pagina_recibe_url_y_token():
    html = f5.pagina_dormido(f5.PAGINA.read_text(encoding="utf-8"), "https://abc.lambda-url.us-east-2.on.aws/", "tk")
    assert "https://abc.lambda-url.us-east-2.on.aws'" in html and "'tk'" in html and "__" not in html.split("<script>")[1]
    with pytest.raises(ValueError):
        f5.pagina_dormido("<html></html>", "u", "t")


CFG = {
    "Origins": {"Quantity": 1, "Items": [{"Id": "ec2-origen", "DomainName": "ec2-1.us-east-2.compute.amazonaws.com",
                                          "ConnectionAttempts": 3, "ConnectionTimeout": 10}]},
    "CacheBehaviors": {"Quantity": 0},
    "CustomErrorResponses": {"Quantity": 1, "Items": [{"ErrorCode": 404, "ResponsePagePath": "/404.html",
                                                       "ResponseCode": "404", "ErrorCachingMinTTL": 10}]},
}


def test_ajustar_distribucion():
    nueva = f5.ajustar_distribucion(CFG, "b.s3.us-east-2.amazonaws.com", "OAC1")
    ec2 = f5.origen_ec2(nueva)
    assert (ec2["ConnectionAttempts"], ec2["ConnectionTimeout"]) == (1, 4)
    s3 = next(o for o in nueva["Origins"]["Items"] if o["Id"] == f5.ORIGEN_S3)
    assert s3["OriginAccessControlId"] == "OAC1" and s3["S3OriginConfig"] == {"OriginAccessIdentity": ""}
    assert [c["PathPattern"] for c in nueva["CacheBehaviors"]["Items"]] == ["/dormido/*"]
    codigos = {e["ErrorCode"]: e for e in nueva["CustomErrorResponses"]["Items"]}
    assert set(codigos) == {404, 502, 504}           # 503 no: la app lo responde a propósito
    assert codigos[502]["ResponsePagePath"] == "/dormido/index.html" and codigos[502]["ErrorCachingMinTTL"] == 0
    assert CFG["Origins"]["Quantity"] == 1           # no modifica la configuración original


def test_ajustar_distribucion_es_idempotente():
    una = f5.ajustar_distribucion(CFG, "b.s3.us-east-2.amazonaws.com", "OAC1")
    dos = f5.ajustar_distribucion(una, "b.s3.us-east-2.amazonaws.com", "OAC1")
    assert una == dos and dos["Origins"]["Quantity"] == 2 and dos["CustomErrorResponses"]["Quantity"] == 3


def test_resumen_calibracion():
    r = f5.resumen_calibracion([float(i) for i in range(1, 101)])
    assert r["muestras"] == 100 and r["min"] == 1 and r["max"] == 100 and r["p50"] == 51
    assert f5.resumen_calibracion([]) == {"muestras": 0}
