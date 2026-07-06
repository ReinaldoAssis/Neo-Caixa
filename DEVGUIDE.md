# Helena — Guia de Funcionamento do Sistema

> Documento de referência para entender como o sistema funciona e como implementar novos módulos e funcionalidades.

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Estrutura do Projeto](#2-estrutura-do-projeto)
3. [Ciclo de Vida da Aplicação](#3-ciclo-de-vida-da-aplicação)
4. [O Core](#4-o-core)
5. [Sistema de Banco de Dados](#5-sistema-de-banco-de-dados)
6. [Sistema de Módulos](#6-sistema-de-módulos)
7. [Como Criar um Novo Módulo](#7-como-criar-um-novo-módulo)
8. [Frontend (Svelte 5)](#8-frontend-svelte-5)
9. [Sistema de Roteamento](#9-sistema-de-roteamento)
10. [Comunicação Frontend ↔ Backend](#10-comunicação-frontend--backend)
11. [Build e Distribuição](#11-build-e-distribuição)
12. [Referência Rápida de APIs do Core](#12-referência-rápida-de-apis-do-core)

---

## 1. Visão Geral

Helena é uma plataforma desktop modular construída com **Python + FastAPI + pywebview + Svelte 5**. A aplicação roda como um servidor web local (FastAPI) embutido em uma janela nativa do sistema operacional (pywebview). O frontend é uma SPA em Svelte 5 que se comunica com o backend via HTTP.

```
┌──────────────────────────────────────┐
│             pywebview                 │
│         Janela Desktop Nativa         │
│  ┌────────────────────────────────┐   │
│  │      Svelte 5 (Frontend)       │   │
│  │           fetch()               │   │
│  └──────────────┬─────────────────┘   │
│                 │                     │
│         http://localhost:8754          │
│                 │                     │
│  ┌──────────────▼─────────────────┐   │
│  │         FastAPI (Backend)      │   │
│  │   REST API / Rotas de Módulos  │   │
│  └────────────────────────────────┘   │
└──────────────────────────────────────┘
```

---

## 2. Estrutura do Projeto

```
helena/
├── app/
│   ├── main.py                       # Entry point: inicia FastAPI + pywebview
│   ├── api.py                        # Factory do app FastAPI, registra módulos
│   │
│   ├── core/                         # Núcleo da aplicação (serviços compartilhados)
│   │   ├── __init__.py               # AppContext (singleton com todos os serviços)
│   │   ├── config.py                 # Configurações via pydantic-settings + .env
│   │   ├── logger.py                 # Logger compartilhado
│   │   ├── events.py                 # EventBus para comunicação desacoplada
│   │   ├── database.py               # Interface abstrata de banco de dados
│   │   ├── db_service.py             # Serviço de banco (carrega driver configurado)
│   │   ├── module_registry.py        # Descoberta, carregamento e registro de módulos
│   │   ├── permissions.py            # Gerenciamento de permissões por módulo
│   │   ├── cache.py                  # Cache em memória com suporte a TTL
│   │   └── utils.py                  # Utilitários (IDs, datas, helpers)
│   │
│   ├── modules/                      # Módulos plugáveis da aplicação
│   │   ├── __init__.py
│   │   └── counter/                  # Exemplo: módulo contador
│   │       ├── __init__.py           # Define `router` (FastAPI) + `manifest`
│   │       └── manifest.py           # Metadados do módulo
│   │
│   ├── drivers/                      # Implementações concretas de banco de dados
│   │   ├── __init__.py
│   │   └── tinydb_driver.py          # Driver TinyDB
│   │
│   └── frontend/                     # SPA Svelte 5 + Vite + TailwindCSS v4
│       ├── package.json              # Dependências npm
│       ├── vite.config.ts            # Config Vite (proxy /api → FastAPI)
│       ├── svelte.config.js          # Config Svelte
│       ├── tsconfig.json             # Config TypeScript
│       ├── index.html                # Entry point HTML
│       ├── dist/                     # Build de produção (gerado)
│       └── src/
│           ├── main.ts               # Montagem do app Svelte 5
│           ├── app.css               # TailwindCSS v4 com @theme customizado
│           ├── App.svelte            # Componente raiz (layout + roteador)
│           ├── lib/
│           │   ├── router.svelte.ts  # Hash router reativo (Svelte 5 runes)
│           │   └── utils.ts          # Função `cn()` para classes condicionais
│           └── modules/              # Componentes frontend dos módulos
│               └── counter/
│                   └── Counter.svelte
│
├── scripts/
│   ├── dev.sh                        # Script de desenvolvimento (API + Vite)
│   └── build.sh                      # Script de build completo
├── Makefile                          # Atalhos: dev, build, clean, install
├── requirements.txt                  # Dependências Python
├── helena.spec                       # Spec do PyInstaller (onefile)
└── .gitignore
```

---

## 3. Ciclo de Vida da Aplicação

### Inicialização

1. **`app/main.py`** é o entry point.
2. Cria uma **thread separada** para o servidor FastAPI (`uvicorn`).
3. Na thread principal, cria uma janela nativa com **pywebview** apontando para `http://127.0.0.1:8754`.
4. O pywebview embute um WebView nativo que carrega o frontend.

### Criação do App FastAPI (`app/api.py`)

1. **`AppContext`** é instanciado como singleton em `core/__init__.py`. Ele inicializa todos os serviços do core: config, event_bus, module_registry, database, logger.
2. **`create_app()`** é chamada — é uma factory function.
3. O middleware **CORS** é configurado (necessário para dev com Vite em porta diferente).
4. **`module_registry.discover()`** escaneia o diretório `app/modules/` e carrega todos os módulos.
5. As **rotas FastAPI de cada módulo** são registradas via `app.include_router(router)`.
6. Rotas built-in são criadas: `GET /api/health` e `GET /api/modules`.
7. Se existir o build do frontend (`app/frontend/dist/`), os arquivos estáticos são montados na raiz `/`.

### Inicialização do Frontend

1. O navegador carrega `index.html` → carrega o JS e CSS do build.
2. **`main.ts`** usa `mount(App, { target: document.getElementById('app') })` (API Svelte 5).
3. **`App.svelte`** executa `onMount`:
   - `initRouter()` — inicializa o hash router, define a rota atual.
   - `loadModules()` — faz `fetch("GET /api/modules")` para obter a lista de módulos.
4. O frontend descobre qual é o `default_module` e navega automaticamente para a rota dele via `navigate()`.

---

## 4. O Core

O core é o coração da aplicação. Ele fornece serviços compartilhados que todos os módulos podem usar. **O core nunca depende de nenhum módulo.**

### AppContext (`core/__init__.py`)

Singleton que agrega todos os serviços. Qualquer parte do código pode acessar:

```python
from app.core import app_context

# Acessar serviços
app_context.config          # Settings (pydantic)
app_context.event_bus       # EventBus
app_context.module_registry # ModuleRegistry
app_context.database        # DatabaseService
app_context.logger          # Logger
```

### Config (`core/config.py`)

Usa **pydantic-settings** com suporte a `.env`. Todas as configurações têm prefixo `HELENA_`. Exemplo de `.env`:

```env
HELENA_DEBUG=true
HELENA_PORT=8754
HELENA_DB_DRIVER=tinydb
```

### EventBus (`core/events.py`)

Sistema pub/sub para comunicação desacoplada entre módulos:

```python
# Emitir evento
app_context.event_bus.emit("order:created", {"order_id": 123})

# Ouvir evento
def handle_order_created(data):
    print(f"Pedido {data['order_id']} criado")

app_context.event_bus.on("order:created", handle_order_created)

# Remover listener
app_context.event_bus.off("order:created", handle_order_created)
```

### Logger (`core/logger.py`)

Logger compartilhado que escreve em console + arquivo (`data/logs/app.log`):

```python
from app.core.logger import logger

logger.info("mensagem")
logger.error("erro", exc_info=True)
```

### Permissões (`core/permissions.py`)

Registro de permissões por módulo. Cada módulo declara suas permissões no manifesto.

```python
from app.core.permissions import PermissionManager

pm = PermissionManager()
pm.register("financeiro", ["read", "write", "delete"])
pm.has("financeiro", "read")  # True
```

### Cache (`core/cache.py`)

Cache em memória com suporte a TTL (time-to-live):

```python
from app.core.cache import CacheManager

cache = CacheManager()
cache.set("chave", valor, ttl=300)  # expira em 5 minutos
cache.get("chave")
cache.has("chave")
cache.delete("chave")
```

---

## 5. Sistema de Banco de Dados

O banco de dados é **completamente abstraído**. Módulos nunca acessam TinyDB, SQLite ou qualquer driver diretamente. Eles usam apenas a interface do `DatabaseService`.

### Arquitetura

```
Módulo → DatabaseService → AbstractDatabaseDriver → TinyDBDriver (ou outro)
```

### Interface abstrata (`core/database.py`)

Define os métodos que todo driver deve implementar:

| Método | Descrição |
|--------|-----------|
| `insert(table, data)` | Insere um documento, retorna ID |
| `update(table, doc_id, data)` | Atualiza um documento por ID |
| `delete(table, doc_id)` | Remove um documento por ID |
| `get(table, doc_id)` | Busca um documento por ID |
| `search(table, query)` | Busca documentos por filtro (dict) |
| `all(table)` | Retorna todos os documentos da tabela |
| `count(table, query?)` | Conta documentos (opcionalmente com filtro) |

### DatabaseService (`core/db_service.py`)

Carrega o driver configurado em `settings.DB_DRIVER` e expõe os mesmos métodos. Módulos usam:

```python
from app.core import app_context

db = app_context.database

# Exemplos
doc_id = db.insert("clientes", {"nome": "João", "email": "joao@email.com"})
cliente = db.get("clientes", doc_id)
todos = db.all("clientes")
resultados = db.search("clientes", {"nome": "João"})
db.update("clientes", doc_id, {"email": "novo@email.com"})
db.delete("clientes", doc_id)
```

### Adicionar um novo driver

1. Criar o arquivo em `app/drivers/` (ex: `postgres_driver.py`).
2. Implementar todos os métodos de `AbstractDatabaseDriver`.
3. Alterar `DB_DRIVER` no `.env` ou `config.py`.

---

## 6. Sistema de Módulos

Toda funcionalidade é implementada como um módulo. Cada módulo é autocontido: remover a pasta do módulo remove completamente a funcionalidade.

### Estrutura de um módulo

```
app/modules/meu-modulo/
├── __init__.py    # Exporta `router` (APIRouter) e `manifest` (dict)
└── manifest.py    # Metadados do módulo (opcional, pode estar no __init__.py)
```

Módulos mais complexos podem ter estrutura interna própria (services, repositories, models, etc.), mas o contrato mínimo com o sistema são dois exports:

### `manifest` (dict)

Declara os metadados do módulo:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `name` | str | Sim | Nome legível do módulo |
| `slug` | str | Sim | Identificador único (mesmo nome da pasta) |
| `version` | str | Sim | Versão semântica |
| `description` | str | Não | Descrição do módulo |
| `is_default` | bool | Não | Se `true`, este módulo é a tela inicial |
| `dependencies` | list[str] | Não | Módulos dos quais depende |
| `menus` | list[dict] | Sim | Itens de menu (label, icon, route) |
| `permissions` | list[str] | Não | Permissões que o módulo declara |
| `events_subscriptions` | list[str] | Não | Eventos que o módulo escuta |

### `router` (APIRouter)

FastAPI APIRouter com as rotas do módulo. Deve usar prefixo único (ex: `prefix="/api/meu-modulo"`).

### Descoberta automática

`ModuleRegistry.discover()` usa `pkgutil.iter_modules` para encontrar todas as pastas dentro de `app/modules/`. Para cada pasta:

1. Importa `app.modules.{nome}`.
2. Lê o atributo `manifest`.
3. Lê o atributo `router` (APIRouter do FastAPI).
4. Registra no registry interno.
5. Se `manifest.is_default == True`, marca como módulo padrão.
6. Emite evento `module:loaded`.

As rotas são automaticamente incluídas na app FastAPI em `api.py`.

---

## 7. Como Criar um Novo Módulo

### Passo 1: Criar a pasta do módulo

```bash
mkdir -p app/modules/meu-modulo
```

### Passo 2: Criar `manifest.py`

```python
# app/modules/meu-modulo/manifest.py

manifest = {
    "name": "Meu Módulo",
    "slug": "meu-modulo",
    "version": "1.0.0",
    "description": "Descrição do que o módulo faz",
    "is_default": False,       # True se for a tela inicial
    "dependencies": [],
    "menus": [
        {
            "label": "Meu Módulo",
            "icon": "box",
            "route": "/meu-modulo",
            "order": 1,
        }
    ],
    "permissions": ["read", "write"],
    "events_subscriptions": ["order:created"],
}
```

### Passo 3: Criar `__init__.py` com as rotas da API

```python
# app/modules/meu-modulo/__init__.py

from fastapi import APIRouter
from app.modules.meu_modulo.manifest import manifest

router = APIRouter(prefix="/api/meu-modulo", tags=["Meu Módulo"])

@router.get("/items")
async def list_items():
    return {"items": []}

@router.post("/items")
async def create_item(data: dict):
    return {"id": "123", **data}
```

### Passo 4: Criar o componente frontend

```bash
mkdir -p app/frontend/src/modules/meu-modulo
```

```svelte
<!-- app/frontend/src/modules/meu-modulo/MeuModulo.svelte -->
<script lang="ts">
  let items = $state([]);

  async function load() {
    const res = await fetch("/api/meu-modulo/items");
    const data = await res.json();
    items = data.items;
  }

  load();
</script>

<div class="p-8">
  <h2 class="text-xl font-semibold">Meu Módulo</h2>
  <!-- conteúdo aqui -->
</div>
```

### Passo 5: Registrar o componente no App.svelte

Em `app/frontend/src/App.svelte`:

1. **Importar** o componente no topo:
   ```typescript
   import MeuModulo from "./modules/meu-modulo/MeuModulo.svelte";
   ```

2. **Adicionar bloco `{#if}`** na seção `<main>`:
   ```svelte
   {:else if currentRoute.path === "/meu-modulo"}
     <MeuModulo />
   ```

### Passo 6: Reiniciar

O backend descobre o módulo automaticamente. O frontend precisa de rebuild (`npm run build`) para incluir o novo componente.

---

## 8. Frontend (Svelte 5)

### Stack

| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Svelte | 5.x | Framework reativo (runes mode) |
| Vite | 6.x | Bundler e dev server |
| TypeScript | 5.7+ | Tipagem estática |
| TailwindCSS | 4.x | CSS utilitário |
| bits-ui | 2.x | Componentes headless (shadcn-svelte) |
| lucide-svelte | 0.468+ | Ícones |

### Runes do Svelte 5

O projeto usa o modo **runes** do Svelte 5. Os principais:

| Rune | Uso |
|------|-----|
| `$state(x)` | Declara estado reativo |
| `$derived(expr)` | Valor computado reativo |
| `$effect(() => {...})` | Efeito colateral reativo |
| `$state.snapshot(x)` | Snapshot não-reativo |

Arquivos `.svelte.ts` são processados pelo compilador Svelte e podem usar runes.

### Atenção: Componentes dinâmicos

**Svelte 5 não suporta `<svelte:component this={...}>`** (removido do Svelte 4). Para renderizar componentes condicionalmente, use `{#if}` blocks:

```svelte
<!-- Correto (Svelte 5) -->
{#if route === "/counter"}
  <Counter />
{:else if route === "/dashboard"}
  <Dashboard />
{/if}

<!-- ERRADO — não funciona em Svelte 5 -->
<!-- <svelte:component this={algumComponente} /> -->
```

### TailwindCSS v4

A configuração é feita via CSS, não via `tailwind.config.js`. O tema customizado está em `src/app.css`:

```css
@import "tailwindcss";

@theme {
  --color-background: #ffffff;
  --color-foreground: #0a0a0a;
  --color-muted: #f5f5f5;
  --color-muted-foreground: #737373;
  --color-border: #e5e5e5;
  --color-primary: #18181b;
  --color-primary-foreground: #fafafa;
  --color-accent: #f4f4f5;
  --color-accent-foreground: #18181b;
  --color-ring: #18181b;
  --radius: 0.5rem;
}
```

### Utilitário `cn()`

Função para mesclar classes CSS condicionais (padrão shadcn-svelte):

```typescript
import { cn } from "$lib/utils";

// Exemplo
<div class={cn("base-class", isActive && "active-class", className)} />
```

---

## 9. Sistema de Roteamento

O roteamento é baseado em **hash fragments** (`#/rota`). Isso funciona nativamente no pywebview sem precisar de servidor com suporte a SPA fallback.

### Arquivos envolvidos

- **`src/lib/router.svelte.ts`** — módulo reativo com estado da rota atual.
- **`src/App.svelte`** — layout com sidebar + área principal + `{#if}` blocks para cada módulo.

### API do roteador

```typescript
import { currentRoute, initRouter, navigate } from "$lib/router.svelte.ts";

// Inicializar (chamar no onMount)
initRouter();

// Estado reativo da rota atual (sem o #)
console.log(currentRoute.path); // "/counter"

// Navegar para uma rota
navigate("/counter");
```

### Funcionamento

1. `currentRoute.path` é um `$state({ path: "" })` reativo.
2. `initRouter()` define a rota inicial a partir de `window.location.hash` e registra listener para `hashchange`.
3. Quando o usuário clica num menu ou `navigate()` é chamado, `window.location.hash` é alterado.
4. O evento `hashchange` atualiza `currentRoute.path`.
5. Os `{#if}` blocks em `App.svelte` reagem à mudança.

### Fluxo de carregamento inicial

1. App monta → `onMount` chama `initRouter()` + `loadModules()`.
2. `currentRoute.path` = `"/"` (hash vazio).
3. `loadModules()` faz `GET /api/modules` → recebe `{ default_module: "counter" }`.
4. `$effect` detecta que `ready == true`, `path == "/"`, e há um `default_module`.
5. Chama `navigate("/counter")` → hash muda → `currentRoute.path` = `"/counter"`.
6. `{#if currentRoute.path === "/counter"}` renderiza `<Counter />`.

---

## 10. Comunicação Frontend ↔ Backend

### REST API

Toda comunicação de dados usa `fetch()` para endpoints REST. Exemplo:

```typescript
// GET
const res = await fetch("/api/counter/state");
const data = await res.json();

// POST
const res = await fetch("/api/counter/increment", { method: "POST" });
const data = await res.json();
```

### Proxy no desenvolvimento

Durante desenvolvimento, o Vite dev server (porta 5173) faz proxy das chamadas `/api` para o FastAPI (porta 8754). Configurado em `vite.config.ts`:

```typescript
server: {
  port: 5173,
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8754",
      changeOrigin: true,
    },
  },
},
```

### Em produção

Em produção (build + pywebview), o frontend é servido como arquivo estático pelo próprio FastAPI via `StaticFiles`. As chamadas `fetch("/api/...")` vão diretamente para o mesmo servidor.

### WebSocket

Para atualizações em tempo real, o sistema suporta WebSocket. O proxy no Vite já está configurado para `ws://`. Módulos podem usar WebSocket para push de eventos do backend para o frontend.

---

## 11. Build e Distribuição

### Modos de execução

| Modo | Comando | O que faz |
|------|---------|-----------|
| Desenvolvimento | `make dev` | Inicia FastAPI (:8754) + Vite (:5173) em paralelo |
| Apenas API | `make dev-api` | Só o servidor FastAPI com hot reload |
| Apenas Frontend | `make dev-frontend` | Só o Vite dev server |
| Build | `make build` | Build do frontend + PyInstaller |
| Executável | `make build-bin` | Gera o onefile com PyInstaller |

### Fluxo de build completo

```
make build
  ├── build-frontend: cd app/frontend && npm run build
  │   └── Vite compila Svelte → app/frontend/dist/
  └── build-bin: pyinstaller helena.spec --clean --noconfirm
      └── Gera dist/helena (executável único)
```

### PyInstaller

O `helena.spec` configura:
- **Entry point**: `app/main.py`
- **Dados**: `app/frontend/dist/` → incluído no executável
- **Hidden imports**: uvicorn (para evitar missing modules)
- **Exclusões**: tkinter, matplotlib, numpy, pandas (reduz tamanho)
- **Onefile**: `console=False` (sem terminal visível no Windows)

### Scripts auxiliares

```bash
./scripts/dev.sh      # Inicia API + Vite em paralelo com trap para cleanup
./scripts/build.sh    # Build completo (frontend + PyInstaller)
```

---

## 12. Referência Rápida de APIs do Core

### Módulos podem acessar

```python
from app.core import app_context
```

| Serviço | Acesso | Principais métodos |
|---------|--------|-------------------|
| Config | `app_context.config` | `APP_NAME`, `VERSION`, `DEBUG`, `HOST`, `PORT`, `DB_DRIVER` |
| Logger | `app_context.logger` | `info()`, `error()`, `warning()`, `debug()` |
| EventBus | `app_context.event_bus` | `on(event, handler)`, `off(event, handler)`, `emit(event, data)` |
| Database | `app_context.database` | `insert()`, `update()`, `delete()`, `get()`, `search()`, `all()`, `count()` |
| ModuleRegistry | `app_context.module_registry` | `discover()`, `get(name)`, `all()`, `list()`, `default_module` |

### API HTTP built-in

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/health` | Health check (status + versão) |
| GET | `/api/modules` | Lista módulos instalados + default_module |

### Adicionar rotas no módulo

```python
# app/modules/meu-modulo/__init__.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/meu-modulo", tags=["Meu Módulo"])

@router.get("/dados")
async def get_dados():
    return {"status": "ok"}
```

As rotas são automaticamente registradas pelo sistema. Nenhuma configuração adicional é necessária.

---

## Checklist: Novo Módulo

- [ ] Criar pasta `app/modules/<slug>/`
- [ ] Criar `manifest.py` com `name`, `slug`, `version`, `menus`, `is_default`
- [ ] Criar `__init__.py` exportando `manifest` e `router` (APIRouter)
- [ ] Criar componente Svelte em `app/frontend/src/modules/<slug>/`
- [ ] Importar e registrar componente no `App.svelte` com `{#if}` block
- [ ] Testar com `make dev` e acessar `http://localhost:5173`

---

## Checklist: Novo Driver de Banco

- [ ] Criar arquivo em `app/drivers/<nome>_driver.py`
- [ ] Implementar `AbstractDatabaseDriver` (todos os métodos abstratos)
- [ ] Configurar `DB_DRIVER` no `.env` ou `config.py`
- [ ] Testar com `make dev-api`
