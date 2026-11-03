from django.urls import path

from .views import (
    CategoriasView,
    ClassificarProdutosView,
    ConfirmarNotaView,
    ExtrairProdutosView,
)

urlpatterns = [
    path("produtos/extrair/", ExtrairProdutosView.as_view(), name="produtos-extrair"),
    path(
        "produtos/classificar/",
        ClassificarProdutosView.as_view(),
        name="produtos-classificar",
    ),
    path("categorias/", CategoriasView.as_view(), name="categorias"),
    path("notas/confirmar/", ConfirmarNotaView.as_view(), name="notas-confirmar"),
]
