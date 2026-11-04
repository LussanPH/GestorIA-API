"""Testes da listagem de notas, detalhe e dashboard."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from food_register.models import Categorias, NotasFiscais, ProdutosNotasFiscais

NOTAS_URL = "/api/notas/"
DASHBOARD_URL = "/api/dashboard/"


class ListagemDashboardTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "lista@exemplo.com", "senha123", nome_completo="Lista"
        )
        self.outro = get_user_model().objects.create_user(
            "outro@exemplo.com", "senha123", nome_completo="Outro"
        )
        self.client.force_authenticate(self.user)

        self.cereais = Categorias.objects.get(
            grupo_canonico="Cereais e derivados"
        )
        self.leguminosas = Categorias.objects.get(
            grupo_canonico="Leguminosas e derivados"
        )
        self.bebidas = Categorias.objects.get(grupo_canonico="Bebidas")

        self.nota1 = self._criar_nota("1", self.user, date(2026, 11, 1), "30.00")
        self._criar_produto(self.nota1, "Arroz", "10.00", self.cereais)
        self._criar_produto(self.nota1, "Feijão", "15.00", self.leguminosas)

        self.nota2 = self._criar_nota("2", self.user, date(2026, 10, 15), "8.00")
        self._criar_produto(self.nota2, "Café", "8.00", self.bebidas)

        self.nota_outro = self._criar_nota(
            "3", self.outro, date(2026, 11, 2), "99.00"
        )
        self._criar_produto(
            self.nota_outro, "Picanha", "99.00", self.cereais
        )

    def _criar_nota(self, chave, usuario, data, total):
        return NotasFiscais.objects.create(
            chave_acesso=chave,
            fk_usuario=usuario,
            data_compra=data,
            valor_total=Decimal(total),
            cnpj="",
            nome_estabelecimento="Mercado Teste",
            metodo_pag="pix",
        )

    def _criar_produto(self, nota, nome, total, categoria):
        return ProdutosNotasFiscais.objects.create(
            nota_fk=nota,
            un=Decimal("1.000"),
            valor_unitario=Decimal(total),
            valor_total=Decimal(total),
            nome=nome,
            marca="nao_identificada",
            categoria_fk=categoria,
        )

    def test_lista_somente_notas_do_usuario(self):
        resposta = self.client.get(NOTAS_URL)

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual([nota["chave_acesso"] for nota in dados], ["1", "2"])

        nota1 = dados[0]
        self.assertEqual(nota1["valor_total"], "30.00")
        self.assertEqual(nota1["total_alimentos"], "25.00")
        self.assertEqual(nota1["qtd_produtos"], 2)

        nota2 = dados[1]
        self.assertEqual(nota2["total_alimentos"], "8.00")
        self.assertEqual(nota2["qtd_produtos"], 1)

    def test_lista_filtra_por_periodo(self):
        resposta = self.client.get(
            NOTAS_URL, {"inicio": "2026-11-01", "fim": "2026-11-30"}
        )

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["chave_acesso"], "1")

    def test_lista_periodo_invalido_retorna_400(self):
        resposta = self.client.get(
            NOTAS_URL, {"inicio": "2026-11-02", "fim": "2026-11-01"}
        )
        self.assertEqual(resposta.status_code, 400)

    def test_detalhe_da_nota(self):
        resposta = self.client.get(f"{NOTAS_URL}1/")

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["chave_acesso"], "1")
        self.assertEqual(dados["qtd_produtos"], 2)
        self.assertEqual(dados["total_alimentos"], "25.00")
        self.assertEqual(len(dados["produtos"]), 2)
        self.assertEqual(
            {produto["categoria"] for produto in dados["produtos"]},
            {"Cereais e derivados", "Leguminosas e derivados"},
        )

    def test_detalhe_de_outro_usuario_retorna_404(self):
        self.assertEqual(self.client.get(f"{NOTAS_URL}3/").status_code, 404)

    def test_detalhe_inexistente_retorna_404(self):
        self.assertEqual(self.client.get(f"{NOTAS_URL}999/").status_code, 404)

    def test_dashboard_geral(self):
        resposta = self.client.get(DASHBOARD_URL)

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["total_alimentos"], "33.00")
        self.assertEqual(dados["total_cupons"], "38.00")
        self.assertEqual(dados["qtd_notas"], 2)
        self.assertEqual(dados["qtd_produtos"], 3)
        self.assertIsNone(dados["periodo"]["inicio"])
        self.assertIsNone(dados["periodo"]["fim"])

        por_categoria = {
            item["categoria"]: item["total"]
            for item in dados["por_categoria"]
        }
        self.assertEqual(
            por_categoria,
            {
                "Cereais e derivados": "10.00",
                "Leguminosas e derivados": "15.00",
                "Bebidas": "8.00",
            },
        )
        self.assertEqual(
            dados["por_mes"],
            [
                {"mes": "2026-10", "total": "8.00"},
                {"mes": "2026-11", "total": "25.00"},
            ],
        )

    def test_dashboard_filtra_por_periodo(self):
        resposta = self.client.get(
            DASHBOARD_URL, {"inicio": "2026-11-01", "fim": "2026-11-30"}
        )

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["total_alimentos"], "25.00")
        self.assertEqual(dados["total_cupons"], "30.00")
        self.assertEqual(dados["qtd_notas"], 1)
        self.assertEqual(dados["qtd_produtos"], 2)
        self.assertEqual(
            {item["categoria"] for item in dados["por_categoria"]},
            {"Cereais e derivados", "Leguminosas e derivados"},
        )

    def test_dashboard_periodo_vazio(self):
        resposta = self.client.get(
            DASHBOARD_URL, {"inicio": "2027-01-01", "fim": "2027-01-31"}
        )

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["total_alimentos"], "0.00")
        self.assertEqual(dados["total_cupons"], "0.00")
        self.assertEqual(dados["qtd_notas"], 0)
        self.assertEqual(dados["qtd_produtos"], 0)
        self.assertEqual(dados["por_categoria"], [])
        self.assertEqual(dados["por_mes"], [])

    def test_dashboard_periodo_invalido_retorna_400(self):
        resposta = self.client.get(
            DASHBOARD_URL, {"inicio": "2026-11-02", "fim": "2026-11-01"}
        )
        self.assertEqual(resposta.status_code, 400)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        for url in (NOTAS_URL, f"{NOTAS_URL}1/", DASHBOARD_URL):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (401, 403))
