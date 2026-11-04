from django.db import migrations

# Fonte: os 16 grupos usados no fine-tuning do classificador
# (classificador-alimentos/classificador/grupos.py). A grafia é exata e não
# deve ser alterada sem retreinar o modelo.
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


def seed_categorias(apps, schema_editor):
    Categorias = apps.get_model("food_register", "Categorias")
    for grupo in GRUPOS:
        Categorias.objects.update_or_create(
            grupo_canonico=grupo,
            defaults={"categoria": grupo},
        )


def reverse(apps, schema_editor):
    # Não apaga categorias: elas podem ter produtos vinculados.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("food_register", "0007_categorias_grupo_canonico"),
    ]

    operations = [
        migrations.RunPython(seed_categorias, reverse),
    ]
