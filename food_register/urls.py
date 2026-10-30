from django.urls import path

from .views import ClassificarProdutosView, ExtrairProdutosView

urlpatterns = [
    path("produtos/extrair/", ExtrairProdutosView.as_view(), name="produtos-extrair"),
    path(
        "produtos/classificar/",
        ClassificarProdutosView.as_view(),
        name="produtos-classificar",
    ),
]
