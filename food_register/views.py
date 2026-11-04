from django.db import IntegrityError, transaction
from django.shortcuts import render
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Categorias, NotasFiscais, ProdutosNotasFiscais
from .serializers import (
    CategoriaSerializer,
    ClassificarRequestSerializer,
    ConfirmarNotaSerializer,
    NotaBaseSerializer,
    NotaSerializer,
    ProdutoClassificadoSerializer,
    ProdutoExtraidoSerializer,
    ProdutoSalvoSerializer,
)
from .services.classificacao import ClassificacaoError, classificar_produtos
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


class ClassificarProdutosView(APIView):
    """POST /api/produtos/classificar/  (produtos já revisados pelo usuário)

    200: {"produtos": [...], "resumo": {...}}
    400: payload inválido (lista vazia, n_item duplicado, item sem nome)
    502: classificador indisponível
    Nada é gravado no banco; a gravação acontece em /notas/confirmar/.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entrada = ClassificarRequestSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            resultado = classificar_produtos(entrada.validated_data["produtos"])
        except ClassificacaoError:
            return Response(
                {"detail": "Classificador indisponível. Selecione as categorias manualmente."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "produtos": ProdutoClassificadoSerializer(
                resultado["produtos"], many=True
            ).data,
            "resumo": resultado["resumo"],
        })


class CategoriasView(ListAPIView):
    """GET /api/categorias/ — lista as categorias cadastradas."""
    permission_classes = [IsAuthenticated]
    serializer_class = CategoriaSerializer
    queryset = Categorias.objects.all().order_by("categoria")


class ConfirmarNotaView(APIView):
    """POST /api/notas/confirmar/  (nota revisada + categorias escolhidas)

    201: nota e produtos alimentícios gravados
    400: payload inválido, total incoerente, categoria inexistente ou nenhum
         item alimentício
    409: chave de acesso já cadastrada

    Somente itens com ``alimenticio=True`` são persistidos. Itens não
    alimentícios entram na validação do total, mas são ignorados na gravação.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entrada = ConfirmarNotaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        nota_dados = entrada.validated_data["nota"]
        produtos = entrada.validated_data["produtos"]
        alimentos = [p for p in produtos if p["alimenticio"]]

        if NotasFiscais.objects.filter(
            chave_acesso=nota_dados["chave_acesso"]
        ).exists():
            return Response(
                {"detail": "Esta nota fiscal já foi cadastrada."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                nota = NotasFiscais.objects.create(
                    fk_usuario=request.user,
                    **nota_dados,
                )
                ProdutosNotasFiscais.objects.bulk_create([
                    ProdutosNotasFiscais(
                        nota_fk=nota,
                        un=produto["un"],
                        valor_unitario=produto["valor_unitario"],
                        valor_total=produto["valor_total"],
                        nome=produto["nome"],
                        marca=(produto.get("marca") or "nao_identificada"),
                        categoria_fk_id=produto["categoria_id"],
                    )
                    for produto in alimentos
                ])
        except IntegrityError:
            return Response(
                {"detail": "Esta nota fiscal já foi cadastrada."},
                status=status.HTTP_409_CONFLICT,
            )

        produtos_salvos = ProdutosNotasFiscais.objects.filter(
            nota_fk=nota
        ).select_related("categoria_fk")
        return Response(
            {
                "nota": NotaBaseSerializer(nota).data,
                "produtos": ProdutoSalvoSerializer(
                    produtos_salvos, many=True
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )
