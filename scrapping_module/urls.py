from django.urls import path

from . import views

app_name = "scrapping_module"

urlpatterns = [
    path("nfce/", views.compra, name="compra"),
    path("nfce/qrcode/", views.ConsultarNfceView.as_view(), name="consultar_qrcode"),
]
