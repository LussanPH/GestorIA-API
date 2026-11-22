"""Consulta real da NFC-e do Ceará a partir do link do QR Code.

Fluxo:
1. ``ler_url_qrcode``: valida o link lido no QR Code e separa os campos do
   parâmetro ``p``. A URL do usuário nunca é acessada: só o host é conferido e
   o ``p`` é extraído. Formatos aceitos (os mesmos do site da SEFAZ-CE):

   - v2 online:       chave|2|ambiente|id do CSC|hash
   - v2 contingência: chave|2|ambiente|dia|valor|digVal|id do CSC|hash
                      (tipo de emissão 9 na posição 34 da chave)
   - v3:              chave|3|ambiente

   O QR Code versão 1 (``nVersao=100``, sem ``p``) não é suportado.
2. ``consultar_sefaz_ce``: abre a página ShowNFCe.html (para receber os cookies
   de sessão, como o navegador faz) e faz o POST no endpoint da versão
   (``/nfce/api/notasFiscal/qrcodev2/`` ou ``.../qrcodev3/``), que devolve
   ``{"xml": "<div>...</div>"}``. Apesar do nome da chave, o conteúdo é o HTML
   do DANFE. Quando a nota não é aceita, a resposta traz ``{"erro": "236 - ..."}``.
3. ``parse_danfe_html``: extrai emitente, itens, totais, pagamento e dados da
   nota desse HTML.
4. ``obter_nfce``: junta tudo e devolve no mesmo formato que o front já
   consome (``{"nfce": {...}}``), com alguns campos extras.

Valores monetários são ``Decimal`` e saem como texto ("12.98") no JSON.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html import unescape
from urllib.parse import parse_qs, quote, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

HOSTS_PERMITIDOS = {"nfce.sefaz.ce.gov.br"}
URL_PAGINA = "http://nfce.sefaz.ce.gov.br/pages/ShowNFCe.html"
URL_API_V2 = "http://nfce.sefaz.ce.gov.br/nfce/api/notasFiscal/qrcodev2/"
URL_API_V3 = "http://nfce.sefaz.ce.gov.br/nfce/api/notasFiscal/qrcodev3/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36"
)

UF_CEARA = "23"
MODELO_NFCE = "65"
POS_TIPO_EMISSAO = 34  # posição do tipo de emissão (tpEmis) na chave de 44 dígitos
EMISSAO_CONTINGENCIA_OFFLINE = "9"
VERSOES_SUPORTADAS = ("2", "3")
TOLERANCIA = Decimal("0.01")
MAX_ESTABELECIMENTO, MAX_PAGAMENTO, MAX_DESCRICAO = 60, 20, 255

# Códigos de rejeição da SEFAZ que merecem uma explicação para o usuário.
MENSAGENS_SEFAZ = {
    "201": "Chave de acesso inválida segundo a SEFAZ-CE.",
    "236": "A SEFAZ-CE não encontrou esta nota (os dados do QR Code não conferem). "
           "Confira o QR Code ou tente mais tarde.",
}


class ConsultaNfceError(Exception):
    """Base dos erros da consulta."""


class QRCodeInvalido(ConsultaNfceError):
    """O link não é um QR Code de NFC-e do Ceará que sabemos consultar."""


class SefazIndisponivel(ConsultaNfceError):
    """Falha de rede, timeout ou erro HTTP na SEFAZ."""


class NotaNaoEncontrada(ConsultaNfceError):
    """A SEFAZ respondeu, mas sem uma nota legível."""


@dataclass(frozen=True)
class DadosQRCode:
    chave_acesso: str
    versao_qrcode: str
    tipo_ambiente: str
    identificador_csc: str = ""
    codigo_hash: str = ""  # exatamente como veio no QR Code (a SEFAZ não recebe em minúsculas)
    dia_data_emissao: str = ""  # só na v2 em contingência
    valor_total_nfce: str = ""  # só na v2 em contingência
    dig_val: str = ""  # só na v2 em contingência
    p: str = ""  # parâmetro "p" original, já validado

    @property
    def em_contingencia(self) -> bool:
        return self.versao_qrcode == "2" and self.chave_acesso[POS_TIPO_EMISSAO] == EMISSAO_CONTINGENCIA_OFFLINE

    @property
    def url_api(self) -> str:
        return URL_API_V3 if self.versao_qrcode == "3" else URL_API_V2

    def como_payload(self) -> dict[str, str]:
        """Corpo do POST, com os mesmos nomes que o site da SEFAZ usa em cada versão."""
        payload = {
            "chave_acesso": self.chave_acesso,
            "versao_qrcode": self.versao_qrcode,
            "tipo_ambiente": self.tipo_ambiente,
        }
        if self.versao_qrcode == "3":
            return payload
        if self.em_contingencia:
            payload["dia_data_emissao"] = self.dia_data_emissao
            payload["valor_total_nfce"] = self.valor_total_nfce
            payload["digVal"] = self.dig_val
        payload["identificador_csc"] = self.identificador_csc
        payload["codigo_hash"] = self.codigo_hash
        return payload

    @property
    def url_pagina(self) -> str:
        return f"{URL_PAGINA}?p={quote(self.p, safe='|')}"


# ---------------------------------------------------------------------------
# 1. Link do QR Code
# ---------------------------------------------------------------------------

def dv_chave_valido(chave: str) -> bool:
    """Confere o dígito verificador (módulo 11) da chave de acesso."""
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(chave[:43])))
    resto = soma % 11
    dv = 0 if resto in (0, 1) else 11 - resto
    return dv == int(chave[43])


def ler_url_qrcode(url: str) -> DadosQRCode:
    url = (url or "").strip()
    try:
        u = urlparse(url)
    except ValueError as exc:
        raise QRCodeInvalido("Link do QR Code inválido.") from exc

    if u.scheme not in ("http", "https") or (u.hostname or "").lower() not in HOSTS_PERMITIDOS:
        raise QRCodeInvalido("Só notas do Ceará (nfce.sefaz.ce.gov.br) são suportadas por enquanto.")

    p = parse_qs(u.query).get("p", [""])[0].strip()
    if not p:
        raise QRCodeInvalido(
            "Este QR Code não tem o parâmetro 'p'. QR Codes antigos (versão 1) não são suportados."
        )
    partes = [x.strip() for x in p.split("|")]
    if len(partes) < 3:
        raise QRCodeInvalido("Formato de QR Code não reconhecido.")

    chave, versao, ambiente = partes[:3]
    if not (len(chave) == 44 and chave.isdigit()):
        raise QRCodeInvalido("A chave de acesso deve ter 44 dígitos.")
    if chave[:2] != UF_CEARA or chave[20:22] != MODELO_NFCE:
        raise QRCodeInvalido("A chave não é de uma NFC-e do Ceará.")
    if not dv_chave_valido(chave):
        raise QRCodeInvalido("Chave de acesso com dígito verificador inválido.")
    if versao not in VERSOES_SUPORTADAS:
        raise QRCodeInvalido(f"Versão {versao!r} do QR Code não suportada (aceitas: 2 e 3).")
    if ambiente != "1":
        raise QRCodeInvalido("A nota não é do ambiente de produção.")

    p_validado = "|".join(partes)

    if versao == "3":
        if len(partes) != 3:
            raise QRCodeInvalido("Formato de QR Code versão 3 não suportado (esperado: chave|3|ambiente).")
        return DadosQRCode(chave, versao, ambiente, p=p_validado)

    # Versão 2. A emissão em contingência (tipo de emissão 9) traz 8 campos
    # (chave|2|ambiente|dia|valor|digVal|csc|hash); a online traz 5.
    contingencia = chave[POS_TIPO_EMISSAO] == EMISSAO_CONTINGENCIA_OFFLINE
    esperado = 8 if contingencia else 5
    if len(partes) != esperado:
        raise QRCodeInvalido(
            f"Formato de QR Code versão 2 não suportado: nota {'em contingência' if contingencia else 'online'} "
            f"deveria ter {esperado} campos, mas tem {len(partes)}."
        )

    csc, hash_ = partes[-2], partes[-1]
    if not re.fullmatch(r"[0-9A-Fa-f]{40}", hash_):
        raise QRCodeInvalido("Hash do QR Code inválido.")

    if not contingencia:
        return DadosQRCode(chave, versao, ambiente, csc, hash_, p=p_validado)

    dia, valor, dig_val = partes[3:6]
    if not re.fullmatch(r"\d{2}", dia):
        raise QRCodeInvalido("Dia de emissão do QR Code inválido.")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", valor):
        raise QRCodeInvalido("Valor total do QR Code inválido.")
    if not re.fullmatch(r"[^\s|]+", dig_val):
        raise QRCodeInvalido("Digest value do QR Code inválido.")
    return DadosQRCode(chave, versao, ambiente, csc, hash_, dia, valor, dig_val, p_validado)


# ---------------------------------------------------------------------------
# 2. Chamada à SEFAZ
# ---------------------------------------------------------------------------

def consultar_sefaz_ce(dados: DadosQRCode, session: requests.Session | None = None) -> str:
    """Devolve o HTML do DANFE (valor da chave "xml" da resposta)."""
    timeout = getattr(settings, "SEFAZ_CE_TIMEOUT", 20)
    s = session or requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})

    try:
        # Abre a página primeiro para receber os cookies de sessão do site.
        s.get(dados.url_pagina, timeout=timeout)
        resposta = s.post(
            dados.url_api,
            json=dados.como_payload(),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "http://nfce.sefaz.ce.gov.br",
                "Referer": dados.url_pagina,
            },
            timeout=timeout,
        )
        resposta.raise_for_status()
    except requests.RequestException as exc:
        raise SefazIndisponivel(f"Falha ao consultar a SEFAZ-CE: {exc}") from exc

    try:
        corpo = resposta.json()
    except ValueError as exc:
        raise NotaNaoEncontrada("A SEFAZ-CE não devolveu JSON.") from exc

    html = corpo.get("xml") if isinstance(corpo, dict) else None
    if not html or not isinstance(html, str):
        logger.warning("Resposta da SEFAZ-CE sem 'xml': %r", corpo)
        erro = corpo.get("erro") if isinstance(corpo, dict) else None
        raise NotaNaoEncontrada(mensagem_erro_sefaz(erro))
    return html


def mensagem_erro_sefaz(erro) -> str:
    """'236 - Regra de neg&oacute;cios da NFC-e' -> texto legível para o usuário."""
    texto = " ".join(unescape(erro).split()) if isinstance(erro, str) else ""
    if not texto:
        return "A SEFAZ-CE não encontrou a nota."
    codigo = texto.split(" - ", 1)[0].strip()
    explicacao = MENSAGENS_SEFAZ.get(codigo)
    return f"{explicacao} (erro {codigo})" if explicacao else f"A SEFAZ-CE recusou a consulta: {texto}"


# ---------------------------------------------------------------------------
# 3. Parser do HTML
# ---------------------------------------------------------------------------

def _limpa(texto: str | None) -> str:
    return " ".join((texto or "").replace("\xa0", " ").split())


def _numero_br(texto: str) -> Decimal | None:
    """'0,764' -> 0.764; '1.234,56' -> 1234.56; 'NaN' ou vazio -> None."""
    t = re.sub(r"[^\d,.\-]", "", texto or "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def _valor_apos_rotulo(span) -> str:
    """Texto do <span> sem o <strong> do rótulo ("Qtde.:", "UN:", ...)."""
    if span is None:
        return ""
    for rotulo in span.find_all("strong"):
        rotulo.extract()
    return _limpa(span.get_text())


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_itens(soup) -> list[dict]:
    tabela = soup.find("table", id="tabResult")
    if tabela is None:
        raise NotaNaoEncontrada("O HTML da nota não tem a tabela de itens.")

    itens = []
    for tr in tabela.find_all("tr"):
        desc = tr.find("span", class_="txtTit")
        valor = tr.find("span", class_="valor")
        if desc is None or valor is None:
            continue
        cod = tr.find("span", class_="RCod")
        qtd = _numero_br(_valor_apos_rotulo(tr.find("span", class_="Rqtd")))
        unit = _numero_br(_valor_apos_rotulo(tr.find("span", class_="RvlUnit")))
        total = _numero_br(valor.get_text())
        if qtd is None or unit is None or total is None:
            raise NotaNaoEncontrada(f"Item com valores ilegíveis: {_limpa(desc.get_text())!r}")
        codigo = re.search(r"\d+", cod.get_text()) if cod else None
        itens.append({
            "descricao": _limpa(desc.get_text())[:MAX_DESCRICAO],
            "codigo": codigo.group() if codigo else "",
            "unidade": _valor_apos_rotulo(tr.find("span", class_="RUN")).upper(),
            "un": str(qtd.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
            "valor_unitario": str(_q2(unit)),
            "valor_total": str(_q2(total)),
        })
    if not itens:
        raise NotaNaoEncontrada("A nota não tem itens.")
    return itens


def _parse_totais(soup) -> tuple[dict[str, Decimal], list[dict]]:
    """Linhas de total ("Valor total R$:" etc.) e formas de pagamento."""
    bloco = soup.find("div", id="totalNota")
    totais: dict[str, Decimal] = {}
    pagamentos: list[dict] = []
    if bloco is None:
        return totais, pagamentos

    depois_da_forma = False
    for linha in bloco.find_all("div", recursive=False):
        if linha.get("id") == "linhaForma":
            depois_da_forma = True
            continue
        label = linha.find("label")
        rotulo = _limpa(label.get_text() if label else "")
        classes_label = (label.get("class") or []) if label else []
        valor_span = linha.find("span", class_="totalNumb")
        valor = _numero_br(valor_span.get_text() if valor_span else "")
        if depois_da_forma and "tx" in classes_label:
            if rotulo.lower().startswith("troco") or valor is None:
                continue
            pagamentos.append({"forma": rotulo, "valor": str(_q2(valor))})
        elif valor is not None:
            totais[rotulo.rstrip(":").strip()] = valor
    return totais, pagamentos


def _parse_infos(soup) -> dict:
    infos = soup.find("div", id="infos")
    texto = _limpa(infos.get_text(" ")) if infos else ""
    saida = {"numero": "", "serie": "", "data_compra": None, "data_hora_emissao": None,
             "producao": "Ambiente de Produção" in texto}

    if m := re.search(r"Número:\s*(\d+)", texto):
        saida["numero"] = m.group(1)
    if m := re.search(r"Série:\s*(\d+)", texto):
        saida["serie"] = m.group(1)
    if m := re.search(r"Emissão:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", texto):
        emissao = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M:%S")
        saida["data_compra"] = emissao.date().isoformat()
        saida["data_hora_emissao"] = emissao.isoformat()

    chave = soup.find("span", class_="chave")
    saida["chave_acesso"] = re.sub(r"\D", "", chave.get_text()) if chave else ""
    return saida


def parse_danfe_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    topo = soup.find("div", class_="txtTopo")
    textos = [_limpa(d.get_text()) for d in soup.select("div.txtCenter > div.text")]
    cnpj = next((re.sub(r"\D", "", t) for t in textos if t.upper().startswith("CNPJ")), "")
    endereco = next((t for t in textos if not t.upper().startswith("CNPJ")), "")

    itens = _parse_itens(soup)
    totais, pagamentos = _parse_totais(soup)
    infos = _parse_infos(soup)

    soma_itens = sum((Decimal(i["valor_total"]) for i in itens), Decimal("0"))
    valor_total = totais.get("Valor total R$", soma_itens)
    descontos = totais.get("Descontos R$", Decimal("0"))
    valor_a_pagar = totais.get("Valor a pagar R$", valor_total - descontos)
    qtd_declarada = totais.get("Qtd. total de itens")

    avisos = []
    if qtd_declarada is not None and int(qtd_declarada) != len(itens):
        avisos.append(f"A nota declara {int(qtd_declarada)} itens, mas {len(itens)} foram lidos.")
    if abs(soma_itens - valor_total) > TOLERANCIA:
        avisos.append(f"A soma dos itens ({soma_itens}) difere do valor total da nota ({valor_total}).")
    if not infos["producao"]:
        avisos.append("A nota não indica ambiente de produção.")

    # Forma principal = a de maior valor (o model guarda só uma, até 20 caracteres).
    principal = max(pagamentos, key=lambda p: Decimal(p["valor"]), default=None)

    return {
        # Campos que o front já usa (nfceParaNota)
        "chave_acesso": infos["chave_acesso"],
        "data_compra": infos["data_compra"],
        "nome_estabelecimento": _limpa(topo.get_text() if topo else "")[:MAX_ESTABELECIMENTO],
        "cnpj": cnpj,
        "metodo_pag": (principal["forma"] if principal else "")[:MAX_PAGAMENTO],
        "itens": itens,
        # Extras
        "valor_total": str(_q2(soma_itens)),  # = soma dos itens, como o NotaSerializer exige
        "descontos": str(_q2(descontos)),
        "valor_a_pagar": str(_q2(valor_a_pagar)),
        "pagamentos": pagamentos,
        "endereco_estabelecimento": endereco,
        "numero": infos["numero"],
        "serie": infos["serie"],
        "data_hora_emissao": infos["data_hora_emissao"],
        "avisos": avisos,
    }


# ---------------------------------------------------------------------------
# 4. Tudo junto
# ---------------------------------------------------------------------------

def obter_nfce(dados: DadosQRCode, session: requests.Session | None = None) -> dict:
    nota = parse_danfe_html(consultar_sefaz_ce(dados, session))
    if nota["chave_acesso"] and nota["chave_acesso"] != dados.chave_acesso:
        raise NotaNaoEncontrada("A SEFAZ devolveu uma nota com outra chave de acesso.")
    nota["chave_acesso"] = dados.chave_acesso
    if not nota["data_compra"]:
        raise NotaNaoEncontrada("Não foi possível ler a data de emissão da nota.")
    return {"nfce": nota}
