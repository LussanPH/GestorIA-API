"""Testes do POST /api/produtos/extrair/ com a LLM simulada (sem custo, sem rede).

A nota de teste é o XML fictício nº 1 já convertido em JSON.
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from food_register.models import NotasFiscais
from food_register.services.extracao import ExtracaoError, extrair_produtos
from food_register.services.schemas import ProdutoExtraido

URL = "/api/produtos/extrair/"
ALVO_LLM = "food_register.services.extracao._invocar_llm"

# <numero>1</numero> -> chave_acesso "1"; sem cnpj e metodo_pag (não existem no XML)
NOTA = {
    "chave_acesso": "1",
    "data_compra": "2026-03-23",
    "valor_total": "30.58",
    "itens": [
        {"descricao": "Leite Integral 1L", "un": "2", "valor_unitario": "4.99", "valor_total": "9.98"},
        {"descricao": "Pimentão Verde 1kg", "un": "2", "valor_unitario": "8.90", "valor_total": "17.80"},
        {"descricao": "Caldo de Galinha (6 cubos)", "un": "1", "valor_unitario": "2.80", "valor_total": "2.80"},
    ],
}

RESPOSTA_LLM = [
    ProdutoExtraido(n_item=1, alimenticio=True, nome="Leite integral", marca=None),
    ProdutoExtraido(n_item=2, alimenticio=True, nome="Pimentão verde", marca=None),
    ProdutoExtraido(n_item=3, alimenticio=True, nome="Caldo de galinha", marca=None),
]


def criar_usuario(email="pedro@exemplo.com", nome="Pedro Teste"):
    return get_user_model().objects.create_user(email, "senha123", nome_completo=nome)


class ExtrairProdutosViewTests(APITestCase):
    def setUp(self):
        self.user = criar_usuario()
        self.client.force_authenticate(self.user)

    @patch(ALVO_LLM, return_value=RESPOSTA_LLM)
    def test_resposta_completa(self, _):
        resp = self.client.post(URL, NOTA, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            "nota": {"chave_acesso": "1", "data_compra": "2026-03-23", "valor_total": "30.58",
                     "cnpj": "", "nome_estabelecimento": "", "metodo_pag": ""},
            "produtos": [
                {"n_item": 1, "descricao": "Leite Integral 1L", "nome": "Leite integral",
                 "marca": None, "alimenticio": True, "precisa_revisao": False,
                 "un": "2.000", "valor_unitario": "4.99", "valor_total": "9.98"},
                {"n_item": 2, "descricao": "Pimentão Verde 1kg", "nome": "Pimentão verde",
                 "marca": None, "alimenticio": True, "precisa_revisao": False,
                 "un": "2.000", "valor_unitario": "8.90", "valor_total": "17.80"},
                {"n_item": 3, "descricao": "Caldo de Galinha (6 cubos)", "nome": "Caldo de galinha",
                 "marca": None, "alimenticio": True, "precisa_revisao": False,
                 "un": "1.000", "valor_unitario": "2.80", "valor_total": "2.80"},
            ],
        })

    @patch(ALVO_LLM, return_value=RESPOSTA_LLM)
    def test_llm_recebe_apenas_n_item_e_descricao(self, mock_llm):
        self.client.post(URL, NOTA, format="json")
        self.assertEqual(mock_llm.call_args.args[0], [
            {"n_item": 1, "descricao": "Leite Integral 1L"},
            {"n_item": 2, "descricao": "Pimentão Verde 1kg"},
            {"n_item": 3, "descricao": "Caldo de Galinha (6 cubos)"},
        ])

    def test_total_incoerente(self):
        resp = self.client.post(URL, {**NOTA, "valor_total": "99.00"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("valor_total", resp.json())

    def test_item_incoerente(self):
        itens = [dict(NOTA["itens"][0], valor_total="12.00")]
        resp = self.client.post(URL, {**NOTA, "itens": itens, "valor_total": "12.00"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_chave_com_letras_e_rejeitada(self):
        resp = self.client.post(URL, {**NOTA, "chave_acesso": "abc"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_aceita_chave_real_de_44_digitos_e_cnpj(self):
        with patch(ALVO_LLM, return_value=RESPOSTA_LLM):
            resp = self.client.post(URL, {**NOTA, "chave_acesso": "3" * 44,
                                          "cnpj": "01234567000189", "metodo_pag": "pix",
                                          "nome_estabelecimento": "Supermercado Exemplo"},
                                    format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["nota"]["cnpj"], "01234567000189")
        self.assertEqual(resp.json()["nota"]["nome_estabelecimento"], "Supermercado Exemplo")

    def test_nome_estabelecimento_longo_e_rejeitado(self):
        resp = self.client.post(URL, {**NOTA, "nome_estabelecimento": "X" * 61}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nome_estabelecimento", resp.json())

    @patch(ALVO_LLM, return_value=RESPOSTA_LLM)
    def test_chave_ja_cadastrada_nao_chama_llm(self, mock_llm):
        NotasFiscais.objects.create(chave_acesso="1", fk_usuario=criar_usuario("ana@ex.com", "Ana"),
                                    data_compra=date(2026, 3, 23), valor_total="30.58")
        resp = self.client.post(URL, NOTA, format="json")
        self.assertEqual(resp.status_code, 409)
        mock_llm.assert_not_called()

    @patch(ALVO_LLM, side_effect=ExtracaoError("timeout"))
    def test_falha_da_llm_retorna_502(self, _):
        self.assertEqual(self.client.post(URL, NOTA, format="json").status_code, 502)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.post(URL, NOTA, format="json").status_code, (401, 403))


class ExtrairProdutosServiceTests(TestCase):
    ITENS = [{"descricao": i["descricao"], "un": i["un"], "valor_unitario": i["valor_unitario"],
              "valor_total": i["valor_total"]} for i in NOTA["itens"]]

    @patch(ALVO_LLM)
    def test_reenvia_apenas_itens_omitidos(self, mock_llm):
        mock_llm.side_effect = [RESPOSTA_LLM[:2], [RESPOSTA_LLM[2]]]
        produtos = extrair_produtos(self.ITENS)
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(mock_llm.call_args.args[0], [{"n_item": 3, "descricao": "Caldo de Galinha (6 cubos)"}])
        self.assertFalse(any(p["precisa_revisao"] for p in produtos))

    @patch(ALVO_LLM)
    def test_item_omitido_duas_vezes_vai_para_revisao(self, mock_llm):
        mock_llm.side_effect = [RESPOSTA_LLM[:2], []]
        produtos = extrair_produtos(self.ITENS)
        self.assertTrue(produtos[2]["precisa_revisao"])
        self.assertIsNone(produtos[2]["nome"])

    @patch(ALVO_LLM)
    def test_ignora_inventado_limpa_nao_alimenticio_e_corta_tamanho(self, mock_llm):
        mock_llm.return_value = [
            ProdutoExtraido(n_item=1, alimenticio=True, nome="L" * 150, marca="M" * 80),
            ProdutoExtraido(n_item=2, alimenticio=False, nome="Pimentão", marca="X"),
            RESPOSTA_LLM[2],
            ProdutoExtraido(n_item=99, alimenticio=True, nome="Inventado"),
        ]
        produtos = extrair_produtos(self.ITENS)
        self.assertEqual([p["n_item"] for p in produtos], [1, 2, 3])
        self.assertEqual((len(produtos[0]["nome"]), len(produtos[0]["marca"])), (100, 50))
        self.assertIsNone(produtos[1]["nome"])
        self.assertIsNone(produtos[1]["marca"])
