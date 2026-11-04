"""Testes do GET /api/categorias/."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

URL = "/api/categorias/"


class CategoriasViewTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "cat@exemplo.com", "senha123", nome_completo="Teste Categorias"
        )
        self.client.force_authenticate(self.user)

    def test_lista_as_16_categorias(self):
        resposta = self.client.get(URL)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(len(dados), 16)
        self.assertEqual(
            {item["grupo_canonico"] for item in dados},
            {
                "Cereais e derivados",
                "Leguminosas e derivados",
                "Vegetais e derivados",
                "Frutas e derivados",
                "Leite e derivados",
                "Carnes e derivados",
                "Ovos e derivados",
                "Pescados e Frutos do mar",
                "Gordura e óleos",
                "Sementes e Oleaginosas",
                "Açúcares e doces",
                "Bebidas",
                "Alimentos industrializados",
                "Fast food",
                "Alimentos para fins especiais",
                "Miscelâneas",
            },
        )
        self.assertEqual(set(dados[0]), {"id", "categoria", "grupo_canonico"})

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL).status_code, (401, 403))
