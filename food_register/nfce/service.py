from urllib.parse import urlparse
import re

import requests
from bs4 import BeautifulSoup


SEFAZ_HOSTS = {
    "nfce.sefaz.ce.gov.br",
}


def validar_url(url: str):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("A URL precisa usar HTTP ou HTTPS.")

    if parsed.hostname not in SEFAZ_HOSTS:
        raise ValueError(
            "A URL informada não pertence à SEFAZ-CE."
        )


def extrair_chave_acesso(url: str) -> str:
    chaves = re.findall(r"\d{44}", url)

    if not chaves:
        raise ValueError(
            "Não foi encontrada uma chave de acesso válida na URL."
        )

    return chaves[0]


def consultar_sefaz(url: str):
    validar_url(url)

    chave_acesso = extrair_chave_acesso(url)

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "GestorIA/1.0"
        }
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    return {
        "chave_acesso": chave_acesso,
        "html": response.text,
        "soup": soup,
    }