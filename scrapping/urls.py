from django.urls import path

from .views import decoder_view


urlpatterns = [

    path(
        "qr-code/",
        decoder_view,
        name="decode",
    ),

]