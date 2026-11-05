from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.shortcuts import render
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Categorias, NotasFiscais, ProdutosNotasFiscais
from .serializers import (
    CategoriaSerializer,
    ClassificarRequestSerializer,
    ConfirmarNotaSerializer,
    NotaBaseSerializer,
    NotaDetalheSerializer,
    NotaListaSerializer,
    NotaSerializer,
    PeriodoQuerySerializer,
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


class NotasListView(ListAPIView):
    """GET /api/notas/ — lista as notas do usuário autenticado.

    Aceita ``?inicio=YYYY-MM-DD`` e ``?fim=YYYY-MM-DD``.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotaListaSerializer

    def get_queryset(self):
        parametros = PeriodoQuerySerializer(data=self.request.query_params)
        parametros.is_valid(raise_exception=True)

        queryset = (
            NotasFiscais.objects.filter(fk_usuario=self.request.user)
            .annotate(
                qtd_produtos=Count("produtosnotasfiscais"),
                total_alimentos=Sum(
                    "produtosnotasfiscais__valor_total"
                ),
            )
            .order_by("-data_compra")
        )

        inicio = parametros.validated_data.get("inicio")
        fim = parametros.validated_data.get("fim")
        if inicio:
            queryset = queryset.filter(data_compra__gte=inicio)
        if fim:
            queryset = queryset.filter(data_compra__lte=fim)
        return queryset


class NotaDetailView(RetrieveDestroyAPIView):
    """GET /api/notas/<chave_acesso>/ — detalhe de uma nota do usuário.

    DELETE /api/notas/<chave_acesso>/ — exclui a nota (204). Os produtos saem
    junto (``on_delete=CASCADE``). Nota de outro usuário ou inexistente → 404.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotaDetalheSerializer
    lookup_field = "chave_acesso"

    def get_queryset(self):
        return (
            NotasFiscais.objects.filter(fk_usuario=self.request.user)
            .prefetch_related("produtosnotasfiscais_set__categoria_fk")
        )


class DashboardView(APIView):
    """GET /api/dashboard/ — resumo dos gastos com alimentos.

    Aceita ``?inicio=YYYY-MM-DD`` e ``?fim=YYYY-MM-DD``. Os totais de
    alimentos usam apenas os produtos persistidos (que já são só alimentos).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        parametros = PeriodoQuerySerializer(data=request.query_params)
        parametros.is_valid(raise_exception=True)
        inicio = parametros.validated_data.get("inicio")
        fim = parametros.validated_data.get("fim")

        notas = NotasFiscais.objects.filter(fk_usuario=request.user)
        if inicio:
            notas = notas.filter(data_compra__gte=inicio)
        if fim:
            notas = notas.filter(data_compra__lte=fim)

        produtos = ProdutosNotasFiscais.objects.filter(nota_fk__in=notas)
        total_alimentos = (
            produtos.aggregate(total=Sum("valor_total"))["total"]
            or Decimal("0")
        )
        total_cupons = (
            notas.aggregate(total=Sum("valor_total"))["total"]
            or Decimal("0")
        )

        por_categoria = (
            produtos.values(
                "categoria_fk_id", "categoria_fk__categoria"
            )
            .annotate(
                total=Sum("valor_total"),
                quantidade=Count("id"),
            )
            .order_by("-total")
        )
        por_mes = (
            produtos.annotate(
                ano=ExtractYear("nota_fk__data_compra"),
                mes=ExtractMonth("nota_fk__data_compra"),
            )
            .values("ano", "mes")
            .annotate(total=Sum("valor_total"))
            .order_by("ano", "mes")
        )

        return Response({
            "periodo": {
                "inicio": inicio.isoformat() if inicio else None,
                "fim": fim.isoformat() if fim else None,
            },
            "total_alimentos": f"{total_alimentos:.2f}",
            "total_cupons": f"{total_cupons:.2f}",
            "qtd_notas": notas.count(),
            "qtd_produtos": produtos.count(),
            "por_categoria": [
                {
                    "categoria_id": item["categoria_fk_id"],
                    "categoria": item["categoria_fk__categoria"],
                    "total": f"{item['total']:.2f}",
                    "quantidade": item["quantidade"],
                }
                for item in por_categoria
            ],
            "por_mes": [
                {
                    "mes": f"{item['ano']:04d}-{item['mes']:02d}",
                    "total": f"{item['total']:.2f}",
                }
                for item in por_mes
            ],
        })
