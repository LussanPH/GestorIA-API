import requests
from django.conf import settings

import json
import xmltodict

DEFAULT_GERAR_COMPRAS_URL = "http://localhost:8001/api/gerar-compra/"
DEFAULT_TIMEOUT = 30
counter = 140

class GerarComprasError(Exception):
    """Falha ao consumir o serviço gerar-compras."""


def gerar_compras() -> bytes:
    global counter
    """Faz POST no serviço gerar-compras enviando o counter no corpo e retorna o XML (bytes) recebido."""
    url = getattr(settings, "GERAR_COMPRAS_URL", DEFAULT_GERAR_COMPRAS_URL)
    timeout = getattr(settings, "GERAR_COMPRAS_TIMEOUT", DEFAULT_TIMEOUT)

    try:
        if counter > 0:
            response = requests.post(
                url, json={"counter": counter}, timeout=timeout
            )
            response.raise_for_status()
    except requests.RequestException as exc:
        raise GerarComprasError(str(exc)) from exc

    return response.content

def xml_to_json(xml:bytes):
    data_dict = xmltodict.parse(xml)
    return json.dumps(data_dict)

def decrease_counter():
    global counter
    counter -= 7