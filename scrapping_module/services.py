import requests
from django.conf import settings

DEFAULT_GERAR_COMPRAS_URL = "http://localhost:8001/api/gerar-compra/"
DEFAULT_TIMEOUT = 30


class GerarComprasError(Exception):
    """Falha ao consumir o serviço gerar-compras."""


def gerar_compras() -> bytes:
    """Faz POST no serviço gerar-compras e retorna o XML (bytes) recebido."""
    url = getattr(settings, "GERAR_COMPRAS_URL", DEFAULT_GERAR_COMPRAS_URL)
    timeout = getattr(settings, "GERAR_COMPRAS_TIMEOUT", DEFAULT_TIMEOUT)

    try:
        response = requests.post(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GerarComprasError(str(exc)) from exc

    return response.content