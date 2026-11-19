from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from food_register.models import NotasFiscais

from .consulta_nfce import (
    NotaNaoEncontrada,
    QRCodeInvalido,
    SefazIndisponivel,
    ler_url_qrcode,
    obter_nfce,
)
from .services import GerarComprasError, gerar_compras, xml_to_json, decrease_counter


@require_GET
def compra(request):
    """Nota fictícia do serviço gerar-compras (modo de demonstração)."""
    try:
        xml = gerar_compras()
    except GerarComprasError as exc:
        return JsonResponse(
            {"erro": "Falha ao chamar o serviço gerar-compras", "detalhe": str(exc)},
            status=502,
        )

    decrease_counter()

    response = xml_to_json(xml)

    return HttpResponse(response, content_type="application/json; charset=utf-8")


class QRCodeSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=500)


class ConsultarNfceView(APIView):
    """POST /leitura-qrcode/nfce/qrcode/ com {"url": "<link do QR Code>"}.

    Consulta a NFC-e real na SEFAZ-CE e devolve {"nfce": {...}} no formato do
    front. Nada é gravado no banco.

    400: link inválido ou não suportado
    409: nota já cadastrada (verificado antes de chamar a SEFAZ)
    422: a SEFAZ respondeu, mas não foi possível ler a nota
    502: SEFAZ fora do ar, timeout ou erro HTTP
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        entrada = QRCodeSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            dados = ler_url_qrcode(entrada.validated_data["url"])
        except QRCodeInvalido as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if NotasFiscais.objects.filter(chave_acesso=dados.chave_acesso).exists():
            return Response(
                {"detail": "Esta nota fiscal já foi cadastrada."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            return Response(obter_nfce(dados))
        except SefazIndisponivel as exc:
            return Response(
                {"detail": "Não foi possível consultar a SEFAZ-CE agora. Tente de novo.",
                 "erro": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except NotaNaoEncontrada as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
