"""Testes do POST /api/produtos/classificar/ e do serviço de classificação.

O classificador é sempre simulado: nenhum teste chama o container real.
"""
from unittest.mock import patch

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from food_register.models import Categorias, NotasFiscais, ProdutosNotasFiscais
from food_register.services.classificacao import (
    ClassificacaoError,
    ClassificacaoIndisponivel,
    _post_chat,
    classificar_produtos,
    servidor_disponivel,
)

URL = "/api/produtos/classificar/"
ALVO_DISPONIVEL = "food_register.services.classificacao.servidor_disponivel"
ALVO_CHAT = "food_register.services.classificacao._post_chat"


class RespostaFalsa:
    def __init__(self, dados, status=200):
        self._dados = dados
        self.status_code = status
        self.ok = status < 400

    def json(self):
        return self._dados

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def criar_usuario(email="clf@exemplo.com", nome="Teste Classificação"):
    return get_user_model().objects.create_user(
        email, "senha123", nome_completo=nome
    )


class ClassificarProdutosViewTests(APITestCase):
    def setUp(self):
        self.user = criar_usuario()
        self.client.force_authenticate(self.user)
        self.cereais = Categorias.objects.get(
            grupo_canonico="Cereais e derivados"
        )

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT, return_value="Cereais e derivados")
    def test_classifica_alimento_e_mapeia_categoria(self, mock_chat, _):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz integral",
                        "descricao": "ARROZ INTEGRAL 1KG",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        produto = resposta.json()["produtos"][0]
        self.assertEqual(produto["n_item"], 1)
        self.assertEqual(produto["grupo"], "Cereais e derivados")
        self.assertEqual(produto["categoria_id"], self.cereais.id)
        self.assertEqual(produto["categoria"], "Cereais e derivados")
        self.assertFalse(produto["precisa_revisao"])
        self.assertIsNone(produto["motivo"])
        self.assertEqual(
            resposta.json()["resumo"],
            {
                "total": 1,
                "classificados": 1,
                "para_revisao": 0,
                "nao_alimenticios": 0,
            },
        )
        mock_chat.assert_called_once()

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT)
    def test_nao_alimenticio_nao_chama_classificador(self, mock_chat, _):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": None,
                        "descricao": "DETERGENTE 500ML",
                        "alimenticio": False,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        produto = resposta.json()["produtos"][0]
        self.assertEqual(produto["motivo"], "nao_alimenticio")
        self.assertIsNone(produto["categoria_id"])
        self.assertFalse(produto["precisa_revisao"])
        mock_chat.assert_not_called()

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT, return_value="Comida japonesa")
    def test_saida_invalida_vai_para_revisao(self, mock_chat, _):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Sushi",
                        "descricao": "SUSHI",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        produto = resposta.json()["produtos"][0]
        self.assertTrue(produto["precisa_revisao"])
        self.assertEqual(produto["motivo"], "saida_invalida")
        self.assertIsNone(produto["categoria_id"])
        # uma tentativa normal + uma com a lista de grupos
        self.assertEqual(mock_chat.call_count, 2)

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT, side_effect=["Comida japonesa", "Cereais e derivados"])
    def test_fallback_recupera_grupo_valido(self, mock_chat, _):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "ARROZ",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json()["produtos"][0]["grupo"], "Cereais e derivados"
        )
        self.assertEqual(mock_chat.call_count, 2)

    @patch(ALVO_DISPONIVEL, return_value=False)
    def test_classificador_indisponivel_retorna_502(self, _):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "ARROZ",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 502)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "ARROZ",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )
        self.assertIn(resposta.status_code, (401, 403))

    def test_lista_vazia_e_rejeitada(self):
        resposta = self.client.post(URL, {"produtos": []}, format="json")
        self.assertEqual(resposta.status_code, 400)

    def test_n_item_duplicado_e_rejeitado(self):
        produto = {
            "n_item": 1,
            "nome": "Arroz",
            "descricao": "ARROZ",
            "alimenticio": True,
        }
        resposta = self.client.post(
            URL, {"produtos": [produto, dict(produto)]}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)

    def test_item_alimenticio_sem_nome_e_rejeitado(self):
        resposta = self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": None,
                        "descricao": "",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 400)

    def test_limite_de_itens(self):
        produtos = [
            {
                "n_item": indice,
                "nome": f"Item {indice}",
                "descricao": "",
                "alimenticio": True,
            }
            for indice in range(1, settings.CLASSIFICADOR_MAX_ITENS + 2)
        ]
        resposta = self.client.post(URL, {"produtos": produtos}, format="json")
        self.assertEqual(resposta.status_code, 400)

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT, return_value="Cereais e derivados")
    def test_nao_grava_nota_nem_produtos(self, *_):
        self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "ARROZ",
                        "alimenticio": True,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(NotasFiscais.objects.count(), 0)
        self.assertEqual(ProdutosNotasFiscais.objects.count(), 0)

    @patch("food_register.views.classificar_produtos")
    def test_servico_recebe_apenas_campos_necessarios(self, mock_servico):
        mock_servico.return_value = {
            "produtos": [],
            "resumo": {
                "total": 0,
                "classificados": 0,
                "para_revisao": 0,
                "nao_alimenticios": 0,
            },
        }

        self.client.post(
            URL,
            {
                "produtos": [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "ARROZ",
                        "alimenticio": True,
                        # valores não devem chegar ao classificador
                        "un": "1.000",
                        "valor_unitario": "4.99",
                        "valor_total": "4.99",
                    }
                ]
            },
            format="json",
        )

        enviado = mock_servico.call_args.args[0]
        self.assertEqual(
            enviado,
            [
                {
                    "n_item": 1,
                    "nome": "Arroz",
                    "descricao": "ARROZ",
                    "alimenticio": True,
                }
            ],
        )


class ClassificacaoServiceTests(TestCase):
    def setUp(self):
        self.cereais = Categorias.objects.get(
            grupo_canonico="Cereais e derivados"
        )

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT, return_value="cereais e derivados")
    def test_normaliza_caixa_e_acento(self, mock_chat, _):
        resultado = classificar_produtos(
            [
                {
                    "n_item": 1,
                    "nome": "Arroz",
                    "descricao": "",
                    "alimenticio": True,
                }
            ]
        )

        self.assertEqual(
            resultado["produtos"][0]["categoria_id"], self.cereais.id
        )
        self.assertEqual(
            resultado["produtos"][0]["grupo"], "Cereais e derivados"
        )
        mock_chat.assert_called_once()

    @patch(ALVO_DISPONIVEL, return_value=True)
    @patch(ALVO_CHAT)
    def test_nao_alimenticio_nao_chama_modelo(self, mock_chat, _):
        resultado = classificar_produtos(
            [
                {
                    "n_item": 1,
                    "nome": None,
                    "descricao": "DETERGENTE",
                    "alimenticio": False,
                }
            ]
        )

        self.assertEqual(
            resultado["produtos"][0]["motivo"], "nao_alimenticio"
        )
        mock_chat.assert_not_called()

    @patch(ALVO_DISPONIVEL, return_value=False)
    def test_servidor_indisponivel(self, _):
        with self.assertRaises(ClassificacaoIndisponivel):
            classificar_produtos(
                [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "",
                        "alimenticio": True,
                    }
                ]
            )

    @patch(ALVO_DISPONIVEL, return_value=True)
    def test_sem_categorias_canonicas(self, _):
        Categorias.objects.all().delete()
        with self.assertRaises(ClassificacaoIndisponivel):
            classificar_produtos(
                [
                    {
                        "n_item": 1,
                        "nome": "Arroz",
                        "descricao": "",
                        "alimenticio": True,
                    }
                ]
            )


class ServidorDisponivelTests(TestCase):
    @patch("food_register.services.classificacao.requests.get")
    def test_verdadeiro_quando_responde(self, mock_get):
        mock_get.return_value = RespostaFalsa({})
        self.assertTrue(servidor_disponivel())

    @patch(
        "food_register.services.classificacao.requests.get",
        side_effect=requests.ConnectionError("sem servidor"),
    )
    def test_falso_quando_falha(self, _):
        self.assertFalse(servidor_disponivel())


class PostChatTests(TestCase):
    @patch("food_register.services.classificacao.requests.post")
    def test_extrai_message_content_e_payload(self, mock_post):
        mock_post.return_value = RespostaFalsa(
            {"message": {"content": "Cereais e derivados"}}
        )

        conteudo = _post_chat(
            [{"role": "user", "content": "Classifique o alimento: Arroz"}]
        )

        self.assertEqual(conteudo, "Cereais e derivados")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], settings.MODELO_CLASSIFICADOR)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"], {"temperature": 0})
        self.assertEqual(payload["keep_alive"], -1)

    @patch(
        "food_register.services.classificacao.requests.post",
        return_value=RespostaFalsa({}, status=500),
    )
    def test_http_erro_vira_classificacao_error(self, _):
        with self.assertRaises(ClassificacaoError):
            _post_chat([{"role": "user", "content": "Arroz"}])
