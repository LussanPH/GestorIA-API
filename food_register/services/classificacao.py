"""Serviço de classificação de alimentos via Ollama.

O container ``classificador-alimentos`` serve o Qwen3-0.6B fine-tunado em
``OLLAMA_URL`` (padrão ``http://127.0.0.1:11434``). O modelo devolve texto puro
com um dos 16 grupos; o mapeamento para ``Categorias`` é feito por
``Categorias.grupo_canonico``.
"""
from __future__ import annotations

import logging
import unicodedata
from collections.abc import Mapping, Sequence

import requests
from django.conf import settings

from ..models import Categorias
from .prompts import (
    SYSTEM_PROMPT_CLASSIFICACAO,
    USER_PROMPT_CLASSIFICACAO,
    system_prompt_classificacao_fallback,
)

logger = logging.getLogger(__name__)


class ClassificacaoError(Exception):
    """Falha ao se comunicar com o classificador."""


class ClassificacaoIndisponivel(ClassificacaoError):
    """O container do classificador não está acessível."""


class RespostaInvalida(ClassificacaoError):
    """A resposta não é um dos grupos canônicos."""


def _normalizar(texto: str | None) -> str:
    """Normaliza para comparação: sem acento, minúsculo e espaços únicos."""
    if not texto:
        return ""
    if "</think>" in texto:
        texto = texto.split("</think>")[-1]
    if not texto.strip():
        return ""
    linha = texto.strip().splitlines()[0].strip()
    linha = linha.strip("`'\"“”‘’.,:;!-* ")
    decomposto = unicodedata.normalize("NFKD", linha)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def _mapa_grupos() -> dict[str, Categorias]:
    """Mapeia o grupo normalizado para a linha de ``Categorias``."""
    categorias = Categorias.objects.exclude(grupo_canonico__isnull=True)
    return {
        _normalizar(categoria.grupo_canonico): categoria
        for categoria in categorias
        if categoria.grupo_canonico
    }


def _resolver_grupo(
    texto: str, mapa: Mapping[str, Categorias]
) -> Categorias | None:
    chave = _normalizar(texto)
    if not chave:
        return None
    if chave in mapa:
        return mapa[chave]

    # Fallback: a resposta pode vir prefixada ("Grupo: Cereais...").
    candidatos = [
        (len(grupo), categoria)
        for grupo, categoria in mapa.items()
        if grupo in chave
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda item: item[0])[1]


def _url(caminho: str) -> str:
    return f"{settings.OLLAMA_URL.rstrip('/')}{caminho}"


def servidor_disponivel(timeout: float = 5) -> bool:
    """True se o Ollama do classificador responde em ``/api/tags``."""
    try:
        return requests.get(_url("/api/tags"), timeout=timeout).ok
    except requests.RequestException:
        return False


def _post_chat(
    mensagens: list[dict[str, str]], timeout: float | None = None
) -> str:
    payload = {
        "model": settings.MODELO_CLASSIFICADOR,
        "stream": False,
        "messages": mensagens,
        "options": {"temperature": 0},
        # Inteiro -1: a API do Ollama rejeita a string "-1".
        "keep_alive": -1,
    }
    try:
        resposta = requests.post(
            _url("/api/chat"),
            json=payload,
            timeout=timeout or settings.CLASSIFICADOR_TIMEOUT,
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.RequestException as exc:
        raise ClassificacaoError(
            f"Falha ao chamar o classificador em {settings.OLLAMA_URL}: {exc}"
        ) from exc
    except ValueError as exc:
        raise ClassificacaoError(
            "Resposta do classificador não é JSON válido."
        ) from exc

    try:
        return dados["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ClassificacaoError(
            f"Resposta sem 'message.content': {dados!r}"
        ) from exc


def classificar_alimento(
    nome: str,
    *,
    mapa: Mapping[str, Categorias] | None = None,
    timeout: float | None = None,
) -> str:
    """Classifica um alimento e devolve o grupo canônico.

    Tenta uma vez com o system prompt normal e, se a saída não for um grupo
    válido, tenta uma vez com a lista explícita de grupos do banco.
    """
    mapa = mapa if mapa is not None else _mapa_grupos()
    if not mapa:
        raise ClassificacaoIndisponivel(
            "Nenhuma categoria canônica cadastrada. Rode as migrations."
        )

    mensagens = [
        {"role": "system", "content": SYSTEM_PROMPT_CLASSIFICACAO},
        {
            "role": "user",
            "content": USER_PROMPT_CLASSIFICACAO.format(alimento=nome),
        },
    ]
    categoria = _resolver_grupo(_post_chat(mensagens, timeout), mapa)
    if categoria is None:
        grupos = [
            categoria.grupo_canonico
            for categoria in mapa.values()
            if categoria.grupo_canonico
        ]
        mensagens[0] = {
            "role": "system",
            "content": system_prompt_classificacao_fallback(grupos),
        }
        categoria = _resolver_grupo(_post_chat(mensagens, timeout), mapa)
    if categoria is None:
        raise RespostaInvalida("Saída fora dos grupos válidos.")
    return categoria.grupo_canonico


def classificar_produtos(produtos: Sequence[dict]) -> dict:
    """Classifica uma lista de produtos, sem gravar nada no banco.

    Cada item de entrada precisa de ``n_item``, ``alimenticio`` e de ``nome``
    ou ``descricao``. Itens não alimentícios não são enviados ao modelo e
    voltam com ``motivo="nao_alimenticio"``.
    """
    if not servidor_disponivel():
        raise ClassificacaoIndisponivel(
            "Classificador indisponível. Verifique o container em OLLAMA_URL."
        )

    mapa = _mapa_grupos()
    if not mapa:
        raise ClassificacaoIndisponivel(
            "Nenhuma categoria canônica cadastrada. Rode as migrations."
        )

    resultados: list[dict] = []
    for produto in produtos:
        item = {"n_item": produto["n_item"]}

        if not produto["alimenticio"]:
            item.update(
                {
                    "grupo": None,
                    "categoria_id": None,
                    "categoria": None,
                    "precisa_revisao": False,
                    "motivo": "nao_alimenticio",
                }
            )
            resultados.append(item)
            continue

        nome = (produto.get("nome") or produto.get("descricao") or "").strip()
        if not nome:
            item.update(
                {
                    "grupo": None,
                    "categoria_id": None,
                    "categoria": None,
                    "precisa_revisao": True,
                    "motivo": "nome_ausente",
                }
            )
            resultados.append(item)
            continue

        try:
            grupo = classificar_alimento(nome, mapa=mapa)
        except RespostaInvalida:
            logger.warning("Classificação inválida para %r", nome)
            item.update(
                {
                    "grupo": None,
                    "categoria_id": None,
                    "categoria": None,
                    "precisa_revisao": True,
                    "motivo": "saida_invalida",
                }
            )
            resultados.append(item)
            continue

        categoria = _resolver_grupo(grupo, mapa)
        if categoria is None:
            item.update(
                {
                    "grupo": grupo,
                    "categoria_id": None,
                    "categoria": None,
                    "precisa_revisao": True,
                    "motivo": "categoria_nao_cadastrada",
                }
            )
        else:
            item.update(
                {
                    "grupo": grupo,
                    "categoria_id": categoria.id,
                    "categoria": categoria.categoria,
                    "precisa_revisao": False,
                    "motivo": None,
                }
            )
        resultados.append(item)

    resumo = {
        "total": len(resultados),
        "classificados": sum(
            1 for resultado in resultados if resultado["categoria_id"] is not None
        ),
        "para_revisao": sum(
            1 for resultado in resultados if resultado["precisa_revisao"]
        ),
        "nao_alimenticios": sum(
            1
            for resultado in resultados
            if resultado["motivo"] == "nao_alimenticio"
        ),
    }
    return {"produtos": resultados, "resumo": resumo}
