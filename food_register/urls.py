from django.urls import path

from .views import ExtrairProdutosView

urlpatterns = [
    path("produtos/extrair/", ExtrairProdutosView.as_view(), name="produtos-extrair"),
]
