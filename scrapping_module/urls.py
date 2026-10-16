from django.urls import path

from . import views

app_name = "scrapping_module"

urlpatterns = [
    path("compra/", views.compra, name="compra"),
]