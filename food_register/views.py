from django.shortcuts import render

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .nfce.service import consultar_sefaz
from .nfce.parser import extrair_nfce


@api_view(["POST"])
def consultar_nfce(request):

    url = request.data.get("url")

    if not url:
        return Response(
            {
                "detail": "URL não informada."
            },
            status=400
        )


    html = consultar_sefaz(url)

    dados = extrair_nfce(html)


    return Response(dados)
