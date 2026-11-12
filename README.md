# Rendvest API

API de finanças pessoais construída com Python 3.12, Django, Django REST Framework e PostgreSQL.

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker com Docker Compose

## Configuração local

```bash
cp .env.example .env
```

Edite o `.env` e defina pelo menos `DJANGO_SECRET_KEY` e `POSTGRES_PASSWORD`. Gere uma chave secreta com:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Instale as dependências e crie o ambiente virtual local `.venv`:

```bash
uv sync
```

Inicie o PostgreSQL:

```bash
docker compose up -d
```

O serviço do banco usa `restart: unless-stopped`, mantém os dados em um volume Docker e volta a iniciar após reiniciar o computador, desde que o Docker esteja configurado para iniciar junto com o sistema.

Crie as tabelas:

```bash
uv run python manage.py migrate
```

Carregue dados fictícios para desenvolvimento:

```bash
uv run python manage.py load_fixtures
```

O comando está em `core/management/commands/load_fixtures.py` e carrega os fixtures de usuários, transações e empréstimos. Pode ser executado novamente sem duplicar os registros e só funciona com `DJANGO_DEBUG=True`. O empréstimo de demonstração segue os valores financeiros do contrato (R$ 8.000,00 liberados, R$ 117,98 de IOF e 7 parcelas pelo sistema Price). As credenciais do usuário de demonstração são `demo@rendvest.local` / `RendvestDemo2026!`; use-as somente em desenvolvimento. Os fixtures são exemplos e não devem ser carregados em produção.

Inicie a API:

```bash
uv run python manage.py runserver
```

A API estará disponível em `http://localhost:8000`. Documentação interativa: `/api/docs/`.

## Módulos e endpoints

Os endpoints estão separados por módulo em `/api/v1/auth/`, `/api/v1/users/`, `/api/v1/transactions/` e `/api/v1/loans/`.

## Formato de erros da API

As respostas de erro usam o mesmo formato e códigos definidos em `core/errors.py`:

```json
{
  "code": "RENDVEST_ERROR_0002",
  "message": "Verifique os campos informados.",
  "errors": [
    {
      "field": "amount",
      "message": "O valor deve ser maior que zero."
    }
  ]
}
```

O frontend deve usar `code` para tratar cenários e `message` para apresentar o erro geral. Para erros de formulário, associe cada item de `errors` ao campo indicado por `field`. Mensagens nunca incluem stack trace ou detalhes internos do banco.

| Código | Significado |
|---|---|
| `RENDVEST_ERROR_0001` | E-mail ou senha inválidos |
| `RENDVEST_ERROR_0002` | Dados inválidos; detalhes por campo em `errors` |
| `RENDVEST_ERROR_0003` | Autenticação necessária |
| `RENDVEST_ERROR_0004` | Acesso não permitido |
| `RENDVEST_ERROR_0005` | Recurso não encontrado |
| `RENDVEST_ERROR_0006` | Muitas requisições |
| `RENDVEST_ERROR_0007` | Conflito com o estado do recurso |
| `RENDVEST_ERROR_0008` | Erro interno inesperado |
| `RENDVEST_ERROR_0009` | Banco de dados indisponível |
| `RENDVEST_ERROR_0010` | Token inválido ou expirado |
| `RENDVEST_ERROR_0011` | Falha na validação CSRF |

### Auth

Os tokens JWT são guardados exclusivamente em cookies `HttpOnly`; login e refresh não os incluem no JSON. O access token expira em 15 minutos e o refresh em 7 dias, com rotação e invalidação do token anterior.

| Método | Endpoint | Acesso | Descrição |
|---|---|---|---|
| GET | `/api/v1/auth/csrf/` | Público | Emite o cookie CSRF e retorna o token CSRF |
| POST | `/api/v1/auth/login/` | Público | Faz login e define cookies de autenticação |
| POST | `/api/v1/auth/refresh/` | Público | Renova tokens usando o cookie refresh |
| POST | `/api/v1/auth/logout/` | Público + CSRF | Invalida o refresh token e limpa os cookies |

Antes de chamadas POST/PATCH/PUT/DELETE, obtenha o token CSRF em `/api/v1/auth/csrf/` e envie o valor `csrfToken` no header `X-CSRFToken`. O navegador envia os cookies com `credentials: "include"`; JavaScript não consegue ler os cookies de autenticação. O logout funciona mesmo se o access token já tiver expirado.

Exemplo no frontend:

```js
const csrfResponse = await fetch("/api/v1/auth/csrf/", {
  credentials: "include",
});
const { csrfToken } = await csrfResponse.json();

await fetch("/api/v1/auth/login/", {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": csrfToken,
  },
  body: JSON.stringify({ email, password }),
});
```

### Users

| Método | Endpoint | Acesso | Descrição |
|---|---|---|---|
| POST | `/api/v1/users/` | Público | Cadastro; valida e-mail e senha |
| GET, PATCH, PUT | `/api/v1/users/me/` | Autenticado | Consulta ou atualiza o perfil do próprio usuário |

O perfil não permite alterar e-mail nem acessar dados de outros usuários.

### Transactions

Todos os endpoints exigem autenticação. Cada usuário só consulta e altera os próprios registros.

| Métodos | Endpoint | Operações |
|---|---|---|
| GET | `/api/v1/transactions/` | Listar ganhos e gastos do usuário autenticado |
| GET, POST | `/api/v1/transactions/incomes/` | Listar ganhos e criar ganho |
| GET, PUT, PATCH, DELETE | `/api/v1/transactions/incomes/{uuid}/` | Consultar, atualizar e excluir ganho |
| GET, POST | `/api/v1/transactions/expenses/` | Listar gastos e criar gasto |
| GET, PUT, PATCH, DELETE | `/api/v1/transactions/expenses/{uuid}/` | Consultar, atualizar e excluir gasto |

Cada transação pode informar `bank`, com opções como `itau`, `nubank`, `banco_do_brasil`, `bradesco`, `caixa`, `santander`, `inter`, `c6_bank`, `btg_pactual`, `sicredi`, `sicoob`, `mercado_pago`, `picpay` e `pagbank`. O campo é opcional; vazio representa banco não informado. Use `other` para outra instituição. As listagens também podem filtrar por banco com `?bank=nubank` ou `?type_bank=nubank`.

Exemplo de criação:

```json
{
  "amount": "1250.00",
  "bank": "itau",
  "category": "Salário",
  "description": "Pagamento mensal",
  "occurred_at": "2026-11-01T09:00:00-03:00"
}
```

Listagens são paginadas (20 itens por página). A listagem geral também aceita filtro por `type` (`income` ou `expense`); todas aceitam filtros por `category` ou `occurred_at` e ordenação por `occurred_at`, `amount` ou `created_at`, por exemplo `?ordering=-amount`.

### Loans

Todos os empréstimos, parcelas e pagamentos são privados por usuário autenticado. O valor contratado (`contracted_amount`) é o valor liberado ao cliente; o IOF informado no contrato é armazenado em `iof_amount` e incluído no valor financiado (`financed_amount`). A API gera parcelas pelo sistema Price usando a taxa mensal (`monthly_interest_percentage`) e o prazo. O CET mensal pode ser registrado separadamente em `monthly_cet_percentage`; ele é informativo e não substitui a taxa usada no cálculo.

| Métodos | Endpoint | Operações |
|---|---|---|
| GET, POST | `/api/v1/loans/` | Listar empréstimos ou criar empréstimo |
| GET, PUT, PATCH, DELETE | `/api/v1/loans/{uuid}/` | Consultar, atualizar ou excluir empréstimo |
| GET | `/api/v1/loans/{uuid}/installments/` | Consultar cronograma e situação das parcelas |
| GET, POST | `/api/v1/loans/{uuid}/payments/` | Listar pagamentos ou pagar uma parcela |

Para registrar um pagamento, envie `installment_number`, `amount` e, opcionalmente, `paid_at` (se omitido, usa a data/hora atual). O pagamento pode ser parcial: o sistema mantém o saldo em aberto da parcela, registra a parte de juros primeiro e depois a amortização do principal, e cria um gasto pelo valor efetivamente pago na mesma operação. Não é permitido pagar acima do saldo da parcela; as demais parcelas não são recalculadas. As situações retornadas são `pending`, `partial`, `paid` e `overdue`. A exclusão do empréstimo é impedida quando há pagamentos registrados; alterações nos valores ou prazo também são bloqueadas após o primeiro pagamento.

A listagem de empréstimos pode ser filtrada pelo banco com `?bank=nubank` ou `?type_bank=nubank`.

Exemplo baseado nos parâmetros financeiros do contrato utilizado:

```json
{
  "bank": "nubank",
  "contracted_amount": "8000.00",
  "iof_amount": "117.98",
  "monthly_interest_percentage": "8.4500",
  "monthly_cet_percentage": "8.8880",
  "term_months": 7,
  "started_at": "2026-09-30",
  "first_due_date": "2026-10-30"
}
```

Com esses dados, o valor financiado é R$ 8.117,98, a parcela Price calculada é R$ 1.583,32 e o total contratual arredondado é R$ 11.083,23. Como o contrato exibe sete parcelas arredondadas de R$ 1.583,32 (soma de R$ 11.083,24), a API ajusta a última parcela em R$ 0,01 para que o cronograma feche com o total contratual. Vencimentos que caiam em sábado ou domingo são movidos para a segunda-feira seguinte; feriados não são ajustados automaticamente.

Exemplo de pagamento parcial de R$ 897,00 da primeira parcela:

```json
{
  "installment_number": 1,
  "amount": "897.00",
  "paid_at": "2026-10-30T12:00:00Z"
}
```

O gasto criado registra R$ 897,00, e a parcela fica parcialmente paga com o saldo restante. O histórico de pagamentos inclui o valor destinado a juros e a principal.

## Segurança

- Cadastro executa os validadores de senha do Django; login e operações de auth têm limites de requisição.
- Access tokens curtos, refresh rotativo e blacklist para invalidar refresh tokens no logout.
- Cookies de autenticação `HttpOnly`, `SameSite=Lax` por padrão, `Secure` automaticamente fora do modo debug; login, refresh, logout e operações autenticadas mutáveis exigem CSRF.
- CORS aceita somente origens explicitamente configuradas em `CORS_ALLOWED_ORIGINS`; credenciais são permitidas sem wildcard.
- APIs protegidas por padrão; transações são filtradas pelo usuário autenticado.
- Senhas ficam armazenadas com os hashers seguros padrão do Django; segredo e senha do banco ficam no `.env`, que não deve ser versionado.
- Em produção, use `DJANGO_DEBUG=False`, defina segredos e hosts reais e sirva apenas por HTTPS. O redirecionamento HTTPS é ativado por padrão quando `DEBUG=False`; HSTS deve ser habilitado somente após confirmar HTTPS e o domínio. Se houver proxy reverso, configure-o para encaminhar corretamente HTTPS.
- Em desenvolvimento com `DEBUG=True`, `localhost` e `127.0.0.1` nas portas 3000, 4173 e 5173 são aceitos por padrão. Para outras origens locais, inclua a origem exata em `CORS_ALLOWED_ORIGINS`; `DJANGO_CSRF_TRUSTED_ORIGINS` usa essa allowlist por padrão. Em produção, configure ambos com a origem HTTPS exata do frontend, por exemplo `https://app.example.com`. O frontend precisa enviar `credentials: "include"`. Se frontend e API forem realmente cross-site, configure `JWT_COOKIE_SAMESITE=None` e `JWT_COOKIE_SECURE=True` (HTTPS obrigatório); nunca use `*` com credenciais.
- Os limites de requisição usam o cache local padrão para desenvolvimento. Em produção com múltiplos processos/servidores, configure um cache compartilhado (por exemplo Redis); sem ele, cada processo mantém limites separados.
- Restringir a documentação `/api/docs/` e `/api/schema/` em produção é recomendável se não quiser expor a descrição dos endpoints.

## Testes e qualidade

```bash
uv run python manage.py test --settings=config.test_settings
uv run ruff check .
uv run ruff format --check .
```

Os testes usam SQLite em memória; a aplicação continua usando PostgreSQL.
