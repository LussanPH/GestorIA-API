# GestorIA

Você é um assistente para ajudar na construção do GestorIA, um aplicativo de gestão de gastos com alimentos.
O repositório se chama `geladeira_virtual` (nome antigo); o produto se chama GestorIA.

## Funcionalidades (visão do produto)
1. **Leitura de QR Code da NFC-e**: o usuário cadastra uma compra de supermercado lendo o QR Code da nota fiscal. O backend faz scraping da nota fiscal eletrônica e uma LLM devolve o texto limpo de cada produto (nome por extenso, marca).
2. **Classificação dos alimentos**: depois que o usuário valida e confirma os itens capturados, outra LLM classifica cada produto em uma das categorias pré-cadastradas (`Categorias`).
3. **Dashboard de gastos**: o usuário analisa os gastos num período escolhido por ele (total, por categoria, etc.).

Fluxo: QR Code → scraping da NFC-e → LLM de extração → revisão do usuário → LLM de classificação → persistência → dashboard.

## Stack
- Python 3.13, gerenciado com **uv** (`pyproject.toml` + `uv.lock`)
- Django 6.1 + Django REST Framework
- Autenticação: djoser + SimpleJWT (com blacklist de refresh token)
- PostgreSQL 16 via `docker-compose.yml`
- Frontend separado (Vite) em `localhost:5173`, já liberado no CORS e usado como `DOMAIN` nos links de e-mail do djoser

## Comandos
```bash
docker compose up -d                 # sobe o Postgres (lê .env)
uv sync                              # instala dependências
uv run python manage.py migrate
uv run python manage.py runserver    # API em localhost:8000
uv run python manage.py makemigrations food_register
uv run python manage.py test
```
`.env` (não versionado) precisa de `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

## Estrutura
- `geladeira_virtual/`: projeto Django (settings, urls raiz)
- `food_register/`: app principal
  - `models.py`: `Usuarios` (login por e-mail, `username = None`, exige `nome_completo`), `NotasFiscais` (PK = `chave_acesso` de 44 dígitos; `cnpj` + `nome_estabelecimento` do mercado), `Categorias` (`categoria` exibida + `grupo_canonico` único), `ProdutosNotasFiscais`
  - `serializers.py`: `CustomUserCreateSerializer` (djoser) + serializers da nota (`NotaBaseSerializer`, `NotaSerializer`, `ItemNotaSerializer`, `ProdutoExtraidoSerializer`), da classificação (`ProdutoClassificarSerializer`, `ClassificarRequestSerializer`, `ProdutoClassificadoSerializer`) e da confirmação (`CategoriaSerializer`, `ProdutoConfirmacaoSerializer`, `ConfirmarNotaSerializer`, `ProdutoSalvoSerializer`)
  - `views.py`: `ExtrairProdutosView`, `ClassificarProdutosView`, `CategoriasView`, `ConfirmarNotaView`
  - `urls.py`: `POST /api/produtos/extrair/`, `POST /api/produtos/classificar/`, `GET /api/categorias/` e `POST /api/notas/confirmar/` (incluídos em `api/` no `urls.py` raiz)
  - `services/`: extração via LLM (`extracao.py`, `prompts.py`, `schemas.py`) e classificação via SLM local (`classificacao.py`). O tamanho do lote da extração é `TAMANHO_LOTE` em `extracao.py`.
  - `tests/`: testes de extração (LLM mockada), classificação (classificador mockado), confirmação, categorias e models
- `request_tests.py`: script manual com `requests` para testar os endpoints de auth

## Autenticação (rotas atuais)
- `POST /auth/users/`: cadastro (`email`, `password`, `re_password`, `nome_completo`)
- `POST /auth/jwt/create/`: login (retorna access e refresh)
- `GET /auth/users/me/`: usuário logado (`Authorization: Bearer <access>`)
- `POST /auth/jwt/logout/`: invalida o refresh token
- Recuperação de senha pelo fluxo `reset_password` do djoser. Em dev o e-mail sai no console.

## Classificação (SLM local)
- `POST /api/produtos/classificar/`: recebe `produtos` com `n_item`, `nome`/`descricao` e `alimenticio`; devolve `grupo`, `categoria_id`, `categoria`, `precisa_revisao` e `motivo`. Não grava nada no banco.
- Chama o container `classificador-alimentos` em `OLLAMA_URL` (padrão `http://127.0.0.1:11434`). **Não usa `LLM_MODEL`**; a extração e a classificação são provedores diferentes.
- `Categorias.grupo_canonico` mapeia os 16 grupos semeados pela migration `0008_seed_categorias`. A LLM não cria categorias; grupo sem categoria volta com `precisa_revisao=True`.
- Configuração: `OLLAMA_URL`, `MODELO_CLASSIFICADOR`, `CLASSIFICADOR_TIMEOUT`, `CLASSIFICADOR_MAX_ITENS`.
- Se a primeira resposta sair dos 16 grupos, o serviço tenta uma vez com a lista explícita de grupos.
- Itens não alimentícios não são enviados ao modelo e voltam com `motivo="nao_alimenticio"`.

## Confirmação da nota
- `POST /api/notas/confirmar/`: grava `NotasFiscais` + `ProdutosNotasFiscais` em `transaction.atomic()`, com `fk_usuario=request.user`.
- Apenas itens `alimenticio=True` são persistidos. Itens não alimentícios entram na validação do total, mas são ignorados na gravação.
- `nota.valor_total` é o total do cupom. O dashboard deve somar apenas os produtos alimentícios para "gastos com alimentos".
- `chave_acesso` duplicada → 409. Item alimentício sem categoria, categoria inexistente, `n_item` duplicado ou total incoerente → 400.
- `GET /api/categorias/`: lista `id`, `categoria` e `grupo_canonico` para o front montar o seletor de categorias.

## Convenções
- Nomes de models, campos, variáveis e mensagens em **português** (`NotasFiscais`, `valor_total`, `fk_usuario`, `nota_fk`).
- Valores monetários sempre em `DecimalField` (2 casas); quantidade `un` com 3 casas.
- Use `settings.AUTH_USER_MODEL` / `get_user_model()`, nunca importe `Usuarios` direto em FKs.
- Novas rotas da API devem exigir JWT por padrão (`JWTAuthentication` já é o padrão do DRF).

## Regras para as LLMs (extração e classificação)
- A LLM recebe só o texto necessário (`n_item` + `descricao`). **Valores (`un`, `valor_unitario`, `valor_total`) nunca passam pela LLM**; eles vêm do scraping e são juntados de volta pelo `n_item`.
- Saída estruturada validada com Pydantic. Todo item enviado tem que voltar exatamente uma vez. Itens faltantes são reenviados uma vez e, se ainda faltarem, voltam com `precisa_revisao=True`.
- Itens não alimentícios são identificados (`alimenticio=False`).
- O provedor é configurável via `LLM_MODEL` no formato `provedor:modelo` (LangChain `init_chat_model`). Não fixe um provedor no código.
- Respeite os limites dos campos do model (`nome` ≤ 100, `marca` ≤ 50).
- Nos testes, substitua a chamada à LLM por mock; os testes não devem chamar APIs externas.
- A classificação só usa categorias já existentes em `Categorias` (via `grupo_canonico`); a LLM não cria categorias novas.
- Nada é gravado no banco antes de o usuário confirmar os itens.
