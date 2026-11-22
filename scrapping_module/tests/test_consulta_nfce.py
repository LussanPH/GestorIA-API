"""Testes da leitura do QR Code e da consulta à SEFAZ-CE. Nenhum teste acessa a rede."""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from scrapping_module.consulta_nfce import (
    NotaNaoEncontrada,
    QRCodeInvalido,
    consultar_sefaz_ce,
    dv_chave_valido,
    ler_url_qrcode,
    mensagem_erro_sefaz,
)

BASE_URL = "http://nfce.sefaz.ce.gov.br/pages/ShowNFCe.html"
HASH = "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678"


def chave_valida(tp_emis: str = "1") -> str:
    """Chave de 44 dígitos do CE (UF 23, modelo 65) com dígito verificador correto."""
    base = "23" + "2611" + "06057223000171" + "65" + "001" + "000123456" + tp_emis + "12345678"
    return next(base + str(d) for d in range(10) if dv_chave_valido(base + str(d)))


def link(*campos: str) -> str:
    return f"{BASE_URL}?p={'|'.join(campos)}"


class LerUrlQrCodeTests(SimpleTestCase):
    def test_v2_online(self):
        chave = chave_valida()
        dados = ler_url_qrcode(link(chave, "2", "1", "000001", HASH))
        self.assertEqual(dados.versao_qrcode, "2")
        self.assertFalse(dados.em_contingencia)
        self.assertEqual(dados.como_payload(), {
            "chave_acesso": chave, "versao_qrcode": "2", "tipo_ambiente": "1",
            "identificador_csc": "000001", "codigo_hash": HASH,
        })
        self.assertTrue(dados.url_api.endswith("/qrcodev2/"))

    def test_hash_e_enviado_como_veio_no_qrcode(self):
        dados = ler_url_qrcode(link(chave_valida(), "2", "1", "1", HASH))
        self.assertEqual(dados.codigo_hash, HASH)  # maiúsculas preservadas
        self.assertNotEqual(dados.codigo_hash, HASH.lower())

    def test_v2_contingencia(self):
        chave = chave_valida("9")
        dados = ler_url_qrcode(link(chave, "2", "1", "19", "58.90", "ABCDEF0123456789", "000001", HASH))
        self.assertTrue(dados.em_contingencia)
        self.assertEqual(dados.como_payload(), {
            "chave_acesso": chave, "versao_qrcode": "2", "tipo_ambiente": "1",
            "dia_data_emissao": "19", "valor_total_nfce": "58.90", "digVal": "ABCDEF0123456789",
            "identificador_csc": "000001", "codigo_hash": HASH,
        })
        self.assertTrue(dados.url_api.endswith("/qrcodev2/"))

    def test_v3_so_tem_chave_versao_e_ambiente(self):
        chave = chave_valida()
        dados = ler_url_qrcode(link(chave, "3", "1"))
        self.assertEqual(dados.como_payload(), {
            "chave_acesso": chave, "versao_qrcode": "3", "tipo_ambiente": "1",
        })
        self.assertTrue(dados.url_api.endswith("/qrcodev3/"))
        self.assertEqual(dados.url_pagina, f"{BASE_URL}?p={chave}|3|1")

    def test_v3_com_campos_extras_e_recusada(self):
        with self.assertRaises(QRCodeInvalido):
            ler_url_qrcode(link(chave_valida(), "3", "1", "000001", HASH))

    def test_campos_incompativeis_com_tipo_de_emissao(self):
        # Contingência (tpEmis 9) com 5 campos, e emissão online com 8.
        with self.assertRaises(QRCodeInvalido):
            ler_url_qrcode(link(chave_valida("9"), "2", "1", "000001", HASH))
        with self.assertRaises(QRCodeInvalido):
            ler_url_qrcode(link(chave_valida("1"), "2", "1", "19", "58.90", "ABCDEF01", "000001", HASH))

    def test_contingencia_com_campos_invalidos(self):
        chave = chave_valida("9")
        for dia, valor, dig in [("9", "58.90", "AB"), ("19", "58,90", "AB"), ("19", "58.90", "")]:
            with self.subTest(dia=dia, valor=valor, dig=dig), self.assertRaises(QRCodeInvalido):
                ler_url_qrcode(link(chave, "2", "1", dia, valor, dig, "000001", HASH))

    def test_v1_sem_parametro_p_e_recusada(self):
        url = f"{BASE_URL}?chNFe={chave_valida()}&nVersao=100&tpAmb=1&cIdToken=000001&cHashQRCode={HASH}"
        with self.assertRaisesMessage(QRCodeInvalido, "versão 1"):
            ler_url_qrcode(url)

    def test_versao_desconhecida_e_recusada(self):
        with self.assertRaisesMessage(QRCodeInvalido, "não suportada"):
            ler_url_qrcode(link(chave_valida(), "4", "1"))

    def test_recusa_homologacao_host_estranho_e_chave_ruim(self):
        chave = chave_valida()
        invalidos = [
            link(chave, "2", "2", "1", HASH),  # ambiente de homologação
            f"http://exemplo.com/pages/ShowNFCe.html?p={chave}|3|1",  # host fora da lista
            link(chave[:43] + str((int(chave[43]) + 1) % 10), "3", "1"),  # dígito verificador errado
            link("35" + chave[2:], "3", "1"),  # outro estado
            link(chave, "2", "1", "1", "naoehhash"),  # hash inválido
        ]
        for url in invalidos:
            with self.subTest(url=url), self.assertRaises(QRCodeInvalido):
                ler_url_qrcode(url)


class ConsultarSefazTests(SimpleTestCase):
    def _sessao(self, corpo):
        sessao = MagicMock()
        sessao.post.return_value.json.return_value = corpo
        return sessao

    def test_usa_endpoint_e_payload_de_cada_versao(self):
        casos = [
            (link(chave_valida(), "2", "1", "000001", HASH), "/qrcodev2/", 5),
            (link(chave_valida(), "3", "1"), "/qrcodev3/", 3),
        ]
        for url, sufixo, qtd_campos in casos:
            with self.subTest(sufixo=sufixo):
                sessao = self._sessao({"xml": "<div>nota</div>"})
                html = consultar_sefaz_ce(ler_url_qrcode(url), sessao)
                self.assertEqual(html, "<div>nota</div>")
                chamada = sessao.post.call_args
                self.assertTrue(chamada.args[0].endswith(sufixo))
                self.assertEqual(len(chamada.kwargs["json"]), qtd_campos)

    def test_erro_da_sefaz_vira_mensagem_legivel(self):
        sessao = self._sessao({"erro": "236 - Regra de neg&oacute;cios da NFC-e"})
        with self.assertRaises(NotaNaoEncontrada) as ctx:
            consultar_sefaz_ce(ler_url_qrcode(link(chave_valida(), "3", "1")), sessao)
        self.assertIn("não encontrou esta nota", str(ctx.exception))
        self.assertIn("236", str(ctx.exception))
        self.assertNotIn("&", str(ctx.exception))

    def test_mensagem_de_erro_desconhecido_e_resposta_vazia(self):
        self.assertEqual(
            mensagem_erro_sefaz("999 - Regra de neg&oacute;cios"),
            "A SEFAZ-CE recusou a consulta: 999 - Regra de negócios",
        )
        self.assertEqual(mensagem_erro_sefaz(None), "A SEFAZ-CE não encontrou a nota.")
