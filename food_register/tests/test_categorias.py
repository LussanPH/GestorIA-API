"""Testes da taxonomia de categorias e do seed dos 16 grupos."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from food_register.models import Categorias

GRUPOS = (
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
)


class CategoriasSeedTests(TestCase):
    def test_seed_cria_os_16_grupos(self):
        self.assertEqual(Categorias.objects.count(), 16)
        self.assertEqual(
            set(Categorias.objects.values_list("grupo_canonico", flat=True)),
            set(GRUPOS),
        )

    def test_grupo_canonico_e_unico(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Categorias.objects.create(
                    categoria="Duplicada",
                    grupo_canonico="Cereais e derivados",
                )

    def test_categoria_sem_grupo_canonico_e_permitida(self):
        Categorias.objects.create(categoria="Categoria manual")
        Categorias.objects.create(categoria="Outra categoria manual")
        self.assertEqual(
            Categorias.objects.filter(grupo_canonico__isnull=True).count(), 2
        )
