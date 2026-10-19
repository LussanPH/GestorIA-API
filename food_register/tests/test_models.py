"""Confere os tipos alterados no models.py."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from food_register.models import Categorias, NotasFiscais, ProdutosNotasFiscais


class TiposDosCamposTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pedro@ex.com", "x", nome_completo="Pedro")
        self.nota = NotasFiscais.objects.create(
            chave_acesso="1", fk_usuario=self.user, data_compra=date(2026, 3, 23),
            valor_total=Decimal("30.58"),
        )

    def test_valores_sao_exatos(self):
        cat = Categorias.objects.create(categoria="Laticínios")
        p = ProdutosNotasFiscais.objects.create(
            nota_fk=self.nota, un=Decimal("0.1"), valor_unitario=Decimal("0.10"),
            valor_total=Decimal("0.20"), nome="Teste", categoria_fk=cat,
        )
        p.refresh_from_db()
        self.assertEqual(p.valor_unitario + p.valor_total, Decimal("0.30"))  # com float: 0.30000000000000004

    def test_chave_e_cnpj_guardam_texto(self):
        self.nota.cnpj = "01234567000189"
        self.nota.save()
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.cnpj, "01234567000189")  # zero à esquerda preservado
        NotasFiscais.objects.create(chave_acesso="3" * 44, fk_usuario=self.user,
                                    data_compra=date(2026, 3, 24), valor_total=1)
        self.assertTrue(NotasFiscais.objects.filter(pk="3" * 44).exists())

    def test_marca_pode_ficar_vazia(self):
        cat = Categorias.objects.create(categoria="Hortifruti")
        p = ProdutosNotasFiscais(nota_fk=self.nota, un=2, valor_unitario="8.90",
                                 valor_total="17.80", nome="Pimentão verde", categoria_fk=cat)
        p.full_clean()  # com blank=False em marca, isto levantaria ValidationError
