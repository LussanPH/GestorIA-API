"""Testes do POST /api/notas/confirmar/.

Regra: o total é validado com todos os itens, mas apenas itens
``alimenticio=True`` são gravados.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from food_register.models import Categorias, NotasFiscais, ProdutosNotasFiscais

URL = "/api/notas/confirmar/"


class ConfirmarNotaViewTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "nota@exemplo.com", "senha123", nome_completo="Teste Nota"
        )
        self.client.force_authenticate(self.user)
        self.cereais = Categorias.objects.get(
            grupo_canonico="Cereais e derivados"
        )
        self.leguminosas = Categorias.objects.get(
            grupo_canonico="Leguminosas e derivados"
        )

    def payload(self):
        return {
            "nota": {
                "chave_acesso": "1",
                "data_compra": "2026-11-03",
                "valor_total": "30.00",
                "cnpj": "",
                "nome_estabelecimento": "Mercado Teste",
                "metodo_pag": "pix",
            },
            "produtos": [
                {
                    "n_item": 1,
                    "descricao": "ARROZ INTEGRAL 1KG",
                    "nome": "Arroz integral",
                    "marca": "",
                    "alimenticio": True,
                    "un": "1.000",
                    "valor_unitario": "10.00",
                    "valor_total": "10.00",
                    "categoria_id": self.cereais.id,
                },
                {
                    "n_item": 2,
                    "descricao": "FEIJAO CARIOCA 1KG",
                    "nome": "Feijão carioca",
                    "marca": None,
                    "alimenticio": True,
                    "un": "1.000",
                    "valor_unitario": "15.00",
                    "valor_total": "15.00",
                    "categoria_id": self.leguminosas.id,
                },
                {
                    "n_item": 3,
                    "descricao": "DETERGENTE 500ML",
                    "nome": None,
                    "marca": None,
                    "alimenticio": False,
                    "un": "1.000",
                    "valor_unitario": "5.00",
                    "valor_total": "5.00",
                    "categoria_id": None,
                },
            ],
        }

    def test_grava_nota_e_somente_alimentos(self):
        resposta = self.client.post(URL, self.payload(), format="json")

        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        self.assertEqual(corpo["nota"]["chave_acesso"], "1")
        self.assertEqual(corpo["nota"]["valor_total"], "30.00")
        self.assertEqual(len(corpo["produtos"]), 2)
        self.assertEqual(
            {produto["categoria"] for produto in corpo["produtos"]},
            {"Cereais e derivados", "Leguminosas e derivados"},
        )
        self.assertEqual(
            {produto["marca"] for produto in corpo["produtos"]},
            {"nao_identificada"},
        )

        nota = NotasFiscais.objects.get(chave_acesso="1")
        self.assertEqual(nota.fk_usuario, self.user)
        self.assertEqual(nota.valor_total, Decimal("30.00"))
        self.assertEqual(ProdutosNotasFiscais.objects.count(), 2)
        self.assertFalse(
            ProdutosNotasFiscais.objects.filter(nome__icontains="Detergente").exists()
        )
        # O total persistido é só dos alimentos; o total da nota é o do cupom.
        self.assertEqual(
            sum(p.valor_total for p in ProdutosNotasFiscais.objects.all()),
            Decimal("25.00"),
        )

    def test_chave_duplicada_retorna_409(self):
        self.assertEqual(
            self.client.post(URL, self.payload(), format="json").status_code, 201
        )
        resposta = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(NotasFiscais.objects.count(), 1)
        self.assertEqual(ProdutosNotasFiscais.objects.count(), 2)

    def test_total_incoerente_retorna_400(self):
        dados = self.payload()
        dados["nota"]["valor_total"] = "99.00"
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_item_alimenticio_sem_categoria_retorna_400(self):
        dados = self.payload()
        dados["produtos"][0]["categoria_id"] = None
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_categoria_inexistente_retorna_400(self):
        dados = self.payload()
        dados["produtos"][0]["categoria_id"] = 999999
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_sem_alimentos_retorna_400(self):
        dados = self.payload()
        dados["produtos"] = [dados["produtos"][2]]
        dados["nota"]["valor_total"] = "5.00"
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_n_item_duplicado_retorna_400(self):
        dados = self.payload()
        dados["produtos"][1]["n_item"] = 1
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_valor_do_item_incoerente_retorna_400(self):
        dados = self.payload()
        dados["produtos"][0]["valor_total"] = "11.00"
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_chave_invalida_retorna_400(self):
        dados = self.payload()
        dados["nota"]["chave_acesso"] = "abc"
        resposta = self.client.post(URL, dados, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(NotasFiscais.objects.count(), 0)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        resposta = self.client.post(URL, self.payload(), format="json")
        self.assertIn(resposta.status_code, (401, 403))
        self.assertEqual(NotasFiscais.objects.count(), 0)
