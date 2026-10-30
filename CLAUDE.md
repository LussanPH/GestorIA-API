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
  - `models.py`: `Usuarios` (login por e-mail, `username = None`, exige `nome_completo`), `NotasFiscais` (PK = `chave_acesso` de 44 dígitos; `cnpj` + `nome_estabelecimento` do mercado), `Categorias`, `ProdutosNotasFiscais`
  - `serializers.py`: `CustomUserCreateSerializer` (djoser) + serializers da nota (`NotaSerializer`, `ItemNotaSerializer`, `ProdutoExtraidoSerializer`)
  - `views.py`: `ExtrairProdutosView`
  - `urls.py`: `POST /api/produtos/extrair/` (incluído em `api/` no `urls.py` raiz)
  - `services/`: extração via LLM (`extracao.py`, `prompts.py`, `schemas.py`). O tamanho do lote é `TAMANHO_LOTE` em `extracao.py`.
  - `tests/`: testes de extração (LLM mockada) e dos models
- `request_tests.py`: script manual com `requests` para testar os endpoints de auth

## Autenticação (rotas atuais)
- `POST /auth/users/`: cadastro (`email`, `password`, `re_password`, `nome_completo`)
- `POST /auth/jwt/create/`: login (retorna access e refresh)
- `GET /auth/users/me/`: usuário logado (`Authorization: Bearer <access>`)
- `POST /auth/jwt/logout/`: invalida o refresh token
- Recuperação de senha pelo fluxo `reset_password` do djoser. Em dev o e-mail sai no console.

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
- A classificação só usa categorias já existentes em `Categorias`; a LLM não cria categorias novas.
- Nada é gravado no banco antes de o usuário confirmar os itens.
