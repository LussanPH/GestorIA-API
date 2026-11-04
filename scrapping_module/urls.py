from django.urls import path

from . import views

app_name = "scrapping_module"

urlpatterns = [
    path("nfce/", views.compra, name="compra"),
]