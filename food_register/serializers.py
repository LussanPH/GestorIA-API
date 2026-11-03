from decimal import Decimal

from django.conf import settings
from djoser.serializers import UserCreateSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()

class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User

        fields = ('id', 'email', 'password', 'nome_completo')


# Serializers do POST /api/produtos/extrair/.
#
# Os nomes seguem os campos de NotasFiscais e ProdutosNotasFiscais.
# Não são ModelSerializers: nesta etapa nada é gravado no banco.
#
# Correspondência com o XML fictício:
#   <numero>          -> chave_acesso
#   <data>            -> data_compra
#   <total>           -> valor_total
#   <item>/<produto>  -> descricao   (texto bruto; a LLM gera "nome" e "marca")
#   <quantidade>      -> un
#   <valor_unitario>  -> valor_unitario
#   <valor_total>     -> valor_total

TOLERANCIA = Decimal("0.01")  # arredondamento de centavos


class ItemNotaSerializer(serializers.Serializer):
    descricao = serializers.CharField(max_length=255)
    un = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    valor_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))

    def validate(self, item):
        esperado = item["un"] * item["valor_unitario"]
        if abs(esperado - item["valor_total"]) > TOLERANCIA:
            raise serializers.ValidationError(
                f"'{item['descricao']}': un × valor_unitario = {esperado:.2f}, "
                f"mas valor_total é {item['valor_total']}."
            )
        return item


class NotaSerializer(serializers.Serializer):
    chave_acesso = serializers.RegexField(
        r"^\d{1,44}$", max_length=44,
        error_messages={"invalid": "A chave de acesso deve conter apenas dígitos (até 44)."},
    )
    data_compra = serializers.DateField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    # O XML fictício não traz CNPJ nem método de pagamento.
    # CNPJ: 12 posições alfanuméricas + 2 dígitos verificadores (aceita o CNPJ numérico atual).
    cnpj = serializers.RegexField(r"^[0-9]{12}\d{2}$", required=False, allow_blank=True, default="")
    nome_estabelecimento = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    metodo_pag = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    itens = ItemNotaSerializer(many=True, allow_empty=False)

    def validate(self, nota):
        soma = sum(i["valor_total"] for i in nota["itens"])
        if abs(soma - nota["valor_total"]) > TOLERANCIA:
            raise serializers.ValidationError({
                "valor_total": f"A soma dos itens ({soma}) difere do total da nota ({nota['valor_total']})."
            })
        return nota


class ProdutoExtraidoSerializer(serializers.Serializer):
    n_item = serializers.IntegerField()
    descricao = serializers.CharField()
    nome = serializers.CharField(allow_null=True)
    marca = serializers.CharField(allow_null=True)
    alimenticio = serializers.BooleanField()
    precisa_revisao = serializers.BooleanField()
    un = serializers.DecimalField(max_digits=10, decimal_places=3)
    valor_unitario = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)


# Serializers do POST /api/produtos/classificar/.
# O classificador recebe apenas o necessário para classificar; valores
# (un, valor_unitario, valor_total) não passam pelo modelo.

class ProdutoClassificarSerializer(serializers.Serializer):
    n_item = serializers.IntegerField(min_value=1)
    nome = serializers.CharField(max_length=100, allow_null=True, required=False)
    descricao = serializers.CharField(
        max_length=255, allow_blank=True, required=False, default=""
    )
    alimenticio = serializers.BooleanField()

    def validate(self, item):
        if item["alimenticio"] and not (
            (item.get("nome") or "").strip()
            or (item.get("descricao") or "").strip()
        ):
            raise serializers.ValidationError(
                "Item alimentício precisa de 'nome' ou 'descricao'."
            )
        return item


class ClassificarRequestSerializer(serializers.Serializer):
    produtos = ProdutoClassificarSerializer(many=True, allow_empty=False)

    def validate_produtos(self, produtos):
        if len(produtos) > settings.CLASSIFICADOR_MAX_ITENS:
            raise serializers.ValidationError(
                f"No máximo {settings.CLASSIFICADOR_MAX_ITENS} itens por requisição."
            )
        n_itens = [produto["n_item"] for produto in produtos]
        if len(n_itens) != len(set(n_itens)):
            raise serializers.ValidationError(
                "Cada 'n_item' deve aparecer uma única vez."
            )
        return produtos


class ProdutoClassificadoSerializer(serializers.Serializer):
    n_item = serializers.IntegerField()
    grupo = serializers.CharField(allow_null=True)
    categoria_id = serializers.IntegerField(allow_null=True)
    categoria = serializers.CharField(allow_null=True)
    precisa_revisao = serializers.BooleanField()
    motivo = serializers.CharField(allow_null=True)
