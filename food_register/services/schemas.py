"""Schema Pydantic da saída da LLM de extração.

A LLM recebe apenas {n_item, descricao} e devolve estes campos.
Valores (un, valor_unitario, valor_total) NUNCA passam pela LLM.
Os nomes "nome" e "marca" são os mesmos de ProdutosNotasFiscais.
"""
from pydantic import BaseModel, Field


class ProdutoExtraido(BaseModel):
    n_item: int = Field(description="Mesmo n_item recebido na entrada, sem alterar.")
    alimenticio: bool = Field(
        description="True se o produto é alimento ou bebida para consumo humano."
    )
    nome: str | None = Field(
        default=None,
        description=(
            "Nome do produto por extenso, sem abreviações, sem marca e sem "
            "peso/volume. Null se alimenticio for false."
        ),
    )
    marca: str | None = Field(
        default=None,
        description="Marca do produto, se identificável. Null se não houver ou se não for alimentício.",
    )


class RespostaExtracao(BaseModel):
    produtos: list[ProdutoExtraido]
