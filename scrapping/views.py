from django.shortcuts import render

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from food_register.nfce.service import consultar_sefaz
from food_register.nfce.parser import extrair_nfce


@api_view(["GET", "POST"])
def decoder_view(request):

    if request.method == "GET":
        return render(
            request,
            "test_upload_url.html"
        )

    url = request.data.get("url")

    if not url:
        return Response(
            {
                "detail": "URL não foi informada"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:

        html = consultar_sefaz(url)

        resultado = extrair_nfce(html)

        return Response(
            resultado,
            status=status.HTTP_200_OK,
        )

    except Exception as e:

        return Response(
            {
                "detail": f"Erro ao processar NFC-e: {str(e)}"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )