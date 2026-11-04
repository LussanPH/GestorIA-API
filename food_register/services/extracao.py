"""Serviço de extração de produtos via LLM.

Fluxo:
1. Recebe os itens da nota (com valores) e numera cada um com n_item (1, 2, 3...).
2. Envia à LLM somente {n_item, descricao}, em lotes.
3. Valida a saída: todo n_item enviado precisa voltar, uma única vez.
4. Itens que faltarem são reenviados uma vez; se ainda faltarem,
   voltam marcados com precisa_revisao=True para o usuário preencher.
5. Junta a saída da LLM aos valores originais pelo n_item.
"""
import json
import logging

from django.conf import settings

from .prompts import SYSTEM_PROMPT, USER_PROMPT
from geladeira_virtual.settings import LLM_MODEL
from .schemas import ProdutoExtraido, RespostaExtracao

logger = logging.getLogger(__name__)

MAX_NOME, MAX_MARCA = 100, 50

TAMANHO_LOTE = 30


class ExtracaoError(Exception):
    """Falha ao se comunicar com a LLM."""


def get_llm():
    from langchain.chat_models import init_chat_model

    modelo = init_chat_model(LLM_MODEL, temperature=0)
    return modelo.with_structured_output(RespostaExtracao)


def _invocar_llm(entrada: list[dict]) -> list[ProdutoExtraido]:
    mensagens = [
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT.format(itens_json=json.dumps(entrada, ensure_ascii=False))),
    ]
    try:
        resposta: RespostaExtracao = get_llm().invoke(mensagens)
    except Exception as exc:  # erro de rede, de parsing ou de validação do schema
        raise ExtracaoError(f"Falha na chamada à LLM: {exc}") from exc
    return resposta.produtos


def _extrair_lote(itens: list[dict]) -> dict[int, ProdutoExtraido]:
    esperados = {i["n_item"] for i in itens}
    resultado: dict[int, ProdutoExtraido] = {}

    pendentes = itens
    for tentativa in range(2):
        # só n_item e descrição saem do backend; valores ficam aqui
        entrada = [{"n_item": i["n_item"], "descricao": i["descricao"]} for i in pendentes]
        for p in _invocar_llm(entrada):
            # descarta n_item inventado ou duplicado
            if p.n_item in esperados and p.n_item not in resultado:
                resultado[p.n_item] = p
        pendentes = [i for i in itens if i["n_item"] not in resultado]
        if not pendentes:
            break
        logger.warning(
            "LLM omitiu itens %s (tentativa %d)",
            [i["n_item"] for i in pendentes], tentativa + 1,
        )
    return resultado


def extrair_produtos(itens: list[dict]) -> list[dict]:
    numerados = [{"n_item": n, **item} for n, item in enumerate(itens, start=1)]

    extraidos: dict[int, ProdutoExtraido] = {}
    for inicio in range(0, len(numerados), TAMANHO_LOTE):
        extraidos.update(_extrair_lote(numerados[inicio:inicio + TAMANHO_LOTE]))

    produtos = []
    for item in numerados:
        llm = extraidos.get(item["n_item"])
        if llm is None:
            # LLM falhou duas vezes nesse item: usuário preenche na tela de revisão
            produtos.append({**item, "alimenticio": True, "nome": None,
                             "marca": None, "precisa_revisao": True})
            continue

        alimenticio = llm.alimenticio
        produtos.append({
            **item,  # valores vêm da nota, nunca da LLM
            "alimenticio": alimenticio,
            "nome": llm.nome[:MAX_NOME] if alimenticio and llm.nome else None,
            "marca": llm.marca[:MAX_MARCA] if alimenticio and llm.marca else None,
            "precisa_revisao": alimenticio and not llm.nome,
        })
    return produtos
