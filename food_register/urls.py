from django.urls import path

from .views import consultar_nfce_view


urlpatterns = [
    path(
        "nfce/consultar/",
        consultar_nfce_view,
        name="consultar-nfce",
    ),
]