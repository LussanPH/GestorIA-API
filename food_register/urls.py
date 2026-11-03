from django.urls import path

from .views import (
    CategoriasView,
    ClassificarProdutosView,
    ConfirmarNotaView,
    DashboardView,
    ExtrairProdutosView,
    NotaDetailView,
    NotasListView,
)

urlpatterns = [
    path("produtos/extrair/", ExtrairProdutosView.as_view(), name="produtos-extrair"),
    path(
        "produtos/classificar/",
        ClassificarProdutosView.as_view(),
        name="produtos-classificar",
    ),
    path("categorias/", CategoriasView.as_view(), name="categorias"),
    # "notas/confirmar/" precisa vir antes do detalhe dinâmico.
    path("notas/confirmar/", ConfirmarNotaView.as_view(), name="notas-confirmar"),
    path("notas/", NotasListView.as_view(), name="notas"),
    path(
        "notas/<str:chave_acesso>/",
        NotaDetailView.as_view(),
        name="nota-detalhe",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
