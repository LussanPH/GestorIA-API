from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NotasFiscais
from .serializers import NotaSerializer, ProdutoExtraidoSerializer
from .services.extracao import ExtracaoError, extrair_produtos

# Create your views here.


class ExtrairProdutosView(APIView):
    """POST /api/produtos/extrair/  (JSON da nota confirmado pelo usuário)

    200: {"nota": {... sem itens}, "produtos": [...]}
    400: JSON inválido ou valores incoerentes
    409: chave de acesso já cadastrada
    502: falha na LLM
    Nada é gravado no banco; a gravação acontece em /notas/confirmar/.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entrada = NotaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        nota = entrada.validated_data

        # chave_acesso é a primary key: não pode se repetir no banco inteiro
        if NotasFiscais.objects.filter(chave_acesso=nota["chave_acesso"]).exists():
            return Response(
                {"detail": "Esta nota fiscal já foi cadastrada."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            produtos = extrair_produtos(nota["itens"])
        except ExtracaoError:
            return Response(
                {"detail": "Não foi possível processar os produtos agora. Tente novamente."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        dados_nota = NotaSerializer(nota).data
        dados_nota.pop("itens")  # os itens voltam enriquecidos em "produtos"
        return Response({
            "nota": dados_nota,
            "produtos": ProdutoExtraidoSerializer(produtos, many=True).data,
        })
