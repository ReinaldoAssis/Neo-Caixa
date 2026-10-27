# Arquitetura — Aplicação Desktop Python + FastAPI + pywebview + Svelte 5 (+ Playwright)

> Documento de arquitetura reutilizável. Descreve o **como** da plataforma
> (não o domínio da aplicação), de forma que a mesma estrutura possa ser
> replicada em outro projeto.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Stack](#2-stack)
3. [Estrutura de diretórios](#3-estrutura-de-diretórios)
4. [Backend — o Core](#4-backend--o-core)
5. [Módulos (contrato de plugin)](#5-módulos-contrato-de-plugin)
6. [Frontend](#6-frontend)
7. [Integração Playwright (automação web)](#7-integração-playwright-automação-web)
8. [Build e distribuição](#8-build-e-distribuição)
9. [Receita para replicar a arquitetura](#9-receita-para-replicar-a-arquitetura)
10. [Convenções](#10-convenções)

---

## 1. Visão geral

Aplicação roda como um **servidor web local (FastAPI)** embutido em uma
**janela nativa do sistema operacional (pywebview)**. O frontend é uma **SPA
Svelte 5** (build estático) servida pelo próprio FastAPI. Toda comunicação é
HTTP/REST (`fetch`). Processos pesados (ex.: automação de navegador com
Playwright) rodam em threads de trabalho para não bloquear o loop do servidor.

```
┌──────────────────────────────────────────────┐
│                pywebview                      │
│            Janela Desktop Nativa              │
│   ┌────────────────────────────────────┐      │
│   │        Svelte 5 SPA (dist/)         │      │
│   │             fetch()                 │      │
│   └───────────────┬────────────────────┘      │
└───────────────────┼───────────────────────────┘
                    │ http://127.0.0.1:<port>
        ┌───────────▼───────────┐
        │      FastAPI          │
        │  REST / rotas módulo  │
        │  StaticFiles (SPA)    │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │         Core          │
        │ config, db, events,   │
        │ registry, logger...   │
        └───────────┬───────────┘
                    │
   ┌────────────────┼─────────────────┐
   ▼                ▼                 ▼
Módulos        Driver de BD      Thread worker
(plugins)      (TinyDB/...)      (Playwright)
```

Fluxo de dependências: **módulo → core**. O core **nunca** depende de módulo.

---

## 2. Stack

| Camada    | Tecnologia                                   |
|-----------|----------------------------------------------|
| Runtime   | Python 3.11+                                  |
| Backend   | FastAPI + Uvicorn                             |
| Desktop   | pywebview                                      |
| Banco     | abstração própria + TinyDB (driver padrão)    |
| Automação | Playwright (Chromium/Chrome)                  |
| Frontend  | Svelte 5 (runes) + Vite + TypeScript          |
| Estilo    | TailwindCSS v4 (config via CSS)               |
| UI bases  | bits-ui, lucide-svelte, clsx, tailwind-merge  |
| Empacote  | PyInstaller (onefile / .app / .exe)           |

Dependências Python (`requirements.txt`):

```
fastapi
uvicorn[standard]
pywebview
tinydb
pydantic-settings
pyinstaller
python-multipart
xlrd
openpyxl
reportlab
playwright
```

---

## 3. Estrutura de diretórios

```
projeto/
├── app/
│   ├── main.py                  # Entry point: thread da API + janela pywebview
│   ├── api.py                   # Factory do FastAPI, monta módulos e estáticos
│   ├── version.py               # __version__ (usado em update/config)
│   │
│   ├── core/                    # Núcleo (serviços compartilhados)
│   │   ├── __init__.py          # AppContext (singleton)
│   │   ├── config.py            # Settings (pydantic-settings + .env)
│   │   ├── logger.py            # Logger (console + arquivo)
│   │   ├── events.py            # EventBus (pub/sub)
│   │   ├── database.py          # ABC do driver de banco
│   │   ├── db_service.py        # Serviço de banco (carrega driver)
│   │   ├── module_registry.py   # Descoberta e registro de módulos
│   │   ├── permissions.py       # Permissões por módulo
│   │   ├── cache.py             # Cache em memória com TTL
│   │   └── utils.py             # Helpers (ids, datas)
│   │
│   ├── modules/                 # Módulos plugáveis (features)
│   │   └── <slug>/
│   │       ├── __init__.py      # expõe `router` (APIRouter) + `manifest`
│   │       ├── manifest.py      # metadados do módulo
│   │       └── ...              # services, parsers, automacao, etc.
│   │
│   ├── drivers/                 # Implementações concretas de banco
│   │   └── tinydb_driver.py
│   │
│   ├── data/                    # Dados em dev (git-ignored)
│   │   ├── <db>.json
│   │   └── logs/app.log
│   │
│   └── frontend/                # SPA Svelte + Vite
│       ├── package.json
│       ├── vite.config.ts
│       ├── svelte.config.js
│       ├── tsconfig.json
│       ├── index.html
│       ├── dist/                # build de produção (gerado)
│       └── src/
│           ├── main.ts
│           ├── app.css
│           ├── App.svelte       # shell + roteador + registro de módulos
│           ├── lib/
│           │   ├── router.svelte.ts   # hash router reativo
│           │   └── utils.ts           # cn()
│           └── modules/<slug>/*.svelte
│
├── scripts/                     # dev.sh, build.sh, build-mac.sh, CLI de teste
├── helena.spec                  # spec do PyInstaller
├── Makefile                     # dev / build / clean / install
├── requirements.txt
└── .env                         # opcional (prefixo de env)
```

---

## 4. Backend — o Core

O core fornece serviços compartilhados. Nenhum módulo acessa banco, config ou
logger de forma direta fora desses serviços.

### 4.1 AppContext (singleton)

`app/core/__init__.py` — ponto único de acesso a todos os serviços:

```python
from app.core.config import settings
from app.core.module_registry import ModuleRegistry
from app.core.events import EventBus
from app.core.logger import logger
from app.core.db_service import DatabaseService

class AppContext:
    def __init__(self):
        self.config = settings
        self.event_bus = EventBus()
        self.module_registry = ModuleRegistry(self.event_bus)
        self.database = DatabaseService(settings)
        self.logger = logger

app_context = AppContext()
```

Uso em qualquer lugar: `from app.core import app_context`.

### 4.2 Config (`core/config.py`)

- `pydantic-settings` com `env_file=".env"` e `env_prefix`.
- Resolve diretórios de dados por SO **e** distingue execução normal de
  execução empacotada (`sys.frozen`):

```python
def _user_data_dir() -> Path:
    app = "AppName"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", ...))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", ...))
    return base / app

def _resolve_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return _user_data_dir()      # app instalado -> dados do usuário
    return Path(__file__).parent.parent / "data"  # dev -> pasta local

class Settings(BaseSettings):
    APP_NAME: str = "AppName"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8754
    WINDOW_WIDTH: int = 1280
    WINDOW_HEIGHT: int = 720
    DATA_DIR: Path = _DATA_DIR
    MODULES_DIR: Path = BASE_DIR / "modules"
    DB_DRIVER: str = "tinydb"
    DB_PATH: Path = _DATA_DIR / "app.json"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = _DATA_DIR / "logs"

    class Config:
        env_file = ".env"
        env_prefix = "APP_"

settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
```

> Regra: **dev grava em `app/data/`; app empacotado grava no diretório de
> dados do usuário**. Isso evita erro de escrita em pasta de instalação.

### 4.3 Logger (`core/logger.py`)

Logger padrão que escreve em console + arquivo, reutilizado por todos:

```python
logger = logging.getLogger(settings.APP_NAME)
# handlers: FileHandler(LOG_DIR/app.log) + StreamHandler(stdout)
```

### 4.4 EventBus (`core/events.py`)

Pub/sub para desacoplar módulos (sem importar um ao outro):

```python
app_context.event_bus.on("algum:evento", handler)
app_context.event_bus.emit("algum:evento", {"x": 1})
app_context.event_bus.off("algum:evento", handler)
```

Handlers são isolados em try/except para um erro não derrubar o emissor.

### 4.5 Camada de banco (abstração)

Três peças: interface abstrata → driver concreto → serviço que carrega o driver.

**Interface** (`core/database.py`):

```python
class AbstractDatabaseDriver(ABC):
    def insert(self, table, data) -> str: ...
    def update(self, table, doc_id, data) -> bool: ...
    def delete(self, table, doc_id) -> bool: ...
    def get(self, table, doc_id) -> Optional[dict]: ...
    def search(self, table, query: dict) -> list[dict]: ...
    def all(self, table) -> list[dict]: ...
    def count(self, table, query=None) -> int: ...
```

**Driver** (`drivers/tinydb_driver.py`) — detalhe importante: TinyDB devolve
`Document` com o id em **atributo** (`doc.doc_id`), não como chave. O driver
resolve ids aceitando tanto o `doc_id` numérico quanto um campo `id` lógico:

```python
def _resolve_doc_ids(self, table, doc_id: str) -> list[int]:
    try:
        return [int(doc_id)]
    except ValueError:
        results = self._table(table).search(Query().id == doc_id)
        return [r.doc_id for r in results]
```

**Serviço** (`core/db_service.py`) escolhe o driver por config e repassa os
métodos. Módulos falam só com `app_context.database`; trocar de banco não
altera módulo algum.

### 4.6 Cache, Permissões e Utils

- **Cache** (`core/cache.py`): dicionário em memória com TTL opcional
  (`set/get/delete/clear/has`).
- **Permissions** (`core/permissions.py`): registro de permissões por módulo
  (`register/has/get_module_permissions/all`).
- **Utils** (`core/utils.py`): `generate_id()` (uuid4), `utcnow()`, `safe_get`.

### 4.7 ModuleRegistry (`core/module_registry.py`)

Descoberta automática via `pkgutil.iter_modules` sobre `app/modules`:

1. Importa `app.modules.<nome>`.
2. Lê `manifest` (dict) e `router` (APIRouter).
3. Guarda o módulo, acumula o router.
4. Marca `is_default` (tela inicial).
5. Emite `module:loaded` no EventBus.

Falha ao carregar um módulo é registrada no log e **não** derruba a app.

### 4.8 Factory FastAPI (`app/api.py`)

```python
def create_app() -> FastAPI:
    app = FastAPI(title=..., version=...)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

    app_context.module_registry.discover()
    for router in app_context.module_registry.routers:
        app.include_router(router)

    # rotas built-in: /api/health, /api/modules, /api/update/*
    ...
    # SPA como estático (html=True => fallback p/ index.html)
    dist = _frontend_dist()   # sys._MEIPASS quando frozen
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    return app
```

`_frontend_dist()` trata empacotamento:

```python
if getattr(sys, "frozen", False):
    return Path(sys._MEIPASS) / "frontend" / "dist"
return Path(__file__).parent / "frontend" / "dist"
```

### 4.9 Entry point (`app/main.py`)

API em **thread separada** (daemon); janela nativa na thread principal:

```python
def run_api():
    uvicorn.run(create_app(), host=settings.HOST, port=settings.PORT)

def main():
    threading.Thread(target=run_api, daemon=True).start()
    webview.create_window(
        title="App",
        url=f"http://{settings.HOST}:{settings.PORT}",
        width=..., height=..., min_size=(800, 600), confirm_close=True,
    )
    webview.start(debug=settings.DEBUG)
```

---

## 5. Módulos (contrato de plugin)

Um módulo é uma pasta em `app/modules/<slug>/`. O contrato mínimo são **dois
exports**: `manifest` e `router`.

### `manifest` (dict)

| Campo                  | Tipo       | Descrição                          |
|------------------------|------------|------------------------------------|
| `name`                 | str        | Nome exibido                       |
| `slug`                 | str        | Igual ao nome da pasta             |
| `version`              | str        | SemVer                              |
| `description`          | str        | Descrição                          |
| `is_default`           | bool       | Tela inicial                        |
| `dependencies`         | list[str]  | Módulos requeridos                 |
| `menus`                | list[dict] | `{label, icon, route, order}`      |
| `permissions`          | list[str]  | Permissões declaradas              |
| `events_subscriptions` | list[str]  | Eventos escutados                  |

### Template de módulo

```python
# app/modules/<slug>/manifest.py
manifest = {
    "name": "Meu Módulo",
    "slug": "<slug>",
    "version": "1.0.0",
    "description": "",
    "is_default": False,
    "dependencies": [],
    "menus": [{"label": "Meu Módulo", "icon": "box", "route": "/<slug>", "order": 1}],
    "permissions": ["read", "write"],
    "events_subscriptions": [],
}
```

```python
# app/modules/<slug>/__init__.py
from fastapi import APIRouter
from app.core import app_context
from app.modules.<slug>.manifest import manifest  # re-exportado

router = APIRouter(prefix="/api/<slug>", tags=["<slug>"])

@router.get("/items")
async def list_items():
    return app_context.database.all("<tabela>")

@router.post("/items")
async def create_item(data: dict):
    new_id = app_context.database.insert("<tabela>", data)
    return {"id": new_id, **data}
```

Módulos maiores organizam internamente `services.py`, `parsers.py`,
`automacao.py`, `constants.py`, `config_*.py`, etc. — o sistema só exige
`manifest` + `router`.

---

## 6. Frontend

### 6.1 Build e stack

- **Vite 6** + `@sveltejs/vite-plugin-svelte` + `@tailwindcss/vite`.
- **Svelte 5 em modo runes**: `$state`, `$derived`, `$effect`, `$props`,
  `$bindable`. Arquivos `.svelte.ts` também usam runes (o compilador processa).
- `main.ts` monta com a API nova: `mount(App, { target })`.
- Tailwind v4 configurado **em CSS** (`@theme`), sem `tailwind.config.js`.
- `cn()` em `lib/utils.ts` (clsx + tailwind-merge).

### 6.2 Vite config — proxy de dev + build

```ts
export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  resolve: { alias: { $lib: path.resolve("./src/lib") } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8754", changeOrigin: true },
      "/ws":  { target: "ws://127.0.0.1:8754", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
```

Em dev o Svelte roda na 5173 e faz proxy de `/api` → FastAPI (8754). Em
produção o FastAPI serve o `dist/` e o `fetch("/api/...")` é same-origin.

### 6.3 Hash router (`lib/router.svelte.ts`)

Hash (`#/rota`) escolhido de propósito: funciona no pywebview sem precisar de
SPA fallback no servidor.

```ts
export const currentRoute = $state({ path: "" });

export function initRouter(): string {
  currentRoute.path = getRouteFromHash();
  window.addEventListener("hashchange", () => {
    currentRoute.path = getRouteFromHash();
  });
  return currentRoute.path;
}

export function navigate(path: string) {
  window.location.hash = path;
}

function getRouteFromHash(): string {
  return window.location.hash.replace("#", "") || "/";
}
```

### 6.4 Shell (`App.svelte`)

- `onMount`: `initRouter()` + `loadModules()` (`GET /api/modules`).
- `$effect`: se rota `"/"` e há `default_module`, navega para o primeiro menu.
- Sidebar lista módulos; `<main>` usa blocos `{#if}` por rota.

> Svelte 5 **removeu** `<svelte:component this={...}>`. Renderize por rota com
> `{#if currentRoute.path === "/x"} <Comp /> {/if}` — é o padrão do projeto.

Registro de componente de módulo no shell:

```svelte
<script lang="ts">
  import MeuModulo from "./modules/<slug>/MeuModulo.svelte";
</script>

<main class="flex-1 overflow-auto">
  {#if currentRoute.path === "/<slug>"}
    <MeuModulo />
  {:else if ...}
  {/if}
</main>
```

### 6.5 Estado reativo compartilhado (`.svelte.ts`)

Para cache/estado que precisa **sobreviver** ao mount/unmount de componentes,
crie um módulo `.svelte.ts` com `$state` no escopo do módulo e funções de
acesso. Exemplo genérico:

```ts
// cache.svelte.ts
let _items: Item[] = $state([]);
let _fetched = $state(false);
let _loading = $state(false);

export const getItems = () => _items;
export const isFetched = () => _fetched;
export const isLoading = () => _loading;

export async function fetchItems() {
  _loading = true;
  try {
    const res = await fetch("/api/<slug>/items");
    if (res.ok) { _items = await res.json(); _fetched = true; }
  } finally { _loading = false; }
}
```

Como o `$state` vive no módulo (não no componente), ele persiste entre
montagens — útil para não refazer chamadas caras (ex.: automação) a cada vez
que um modal abre.

### 6.6 Comunicação

Todo dado passa por `fetch()` REST. Sem lógica de negócio no frontend.
Erros do backend chegam pelo `detail` do FastAPI (`HTTPException`).

---

## 7. Integração Playwright (automação web)

Usada para automatizar sistemas web externos (legados/AngularJS). Padrão
central: **scraper assíncrono + wrapper síncrono + execução fora do event
loop**.

### 7.1 Por que wrappers síncronos

A sync API do Playwright **não pode** rodar dentro de um loop asyncio já
ativo (é o caso do FastAPI). Solução adotada:

- Núcleo do scraper em **async** (`async_playwright`).
- Wrapper **síncrono** que chama `asyncio.run(...)`.
- A rota FastAPI executa o wrapper com `loop.run_in_executor` (thread worker).

Assim o loop do servidor nunca é bloqueado e não ocorre o erro
*"This event loop is already running"*.

### 7.2 Blueprint do scraper (async + context manager)

```python
from dataclasses import dataclass, field, asdict
from typing import Any
import asyncio, sys

class SiteScraper:
    def __init__(self, login: str, senha: str, debug: bool = False):
        self._login, self._senha, self._debug = login, senha, debug

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        opts = {"headless": not self._debug}
        try:
            self._browser = await pw.chromium.launch(channel="chrome", **opts)
        except Exception:
            try:
                self._browser = await pw.chromium.launch(**opts)  # chromium do Playwright
            except Exception as e:
                raise RuntimeError(
                    "Navegador nao encontrado. Instale o Google Chrome ou rode "
                    "'playwright install chromium'."
                ) from e
        self._context = await self._browser.new_context()  # accept_downloads=True por padrão
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, *args):
        if getattr(self, "_keep_open", False):   # permite deixar aberto p/ acao manual
            return
        if getattr(self, "_browser", None):
            await self._browser.close()

    async def login(self) -> bool:
        await self._page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await self._page.wait_for_timeout(3000)
        await self._page.fill("#usuario", self._login)
        await self._page.fill("#senha", self._senha)
        await self._page.press("#senha", "Enter")
        await self._page.wait_for_timeout(5000)
        return "login" not in self._page.url.lower()

    async def executar(self) -> dict[str, Any]:
        if not await self.login():
            return {"erro": "Falha no login."}
        # ... navegacao, coleta, retorno serializavel (dict) ...
        return {"ok": True}
```

### 7.3 Wrapper síncrono (API pública do módulo)

```python
def executar_scraper(login: str, senha: str, debug: bool = False) -> dict:
    async def _runner():
        async with SiteScraper(login, senha, debug=debug) as scraper:
            return await scraper.executar()
    try:
        return asyncio.run(_runner())
    except Exception as exc:
        return {"erro": str(exc)}   # nunca deixa exceção crua vazar
```

### 7.4 Chamando a partir do FastAPI (sem bloquear)

```python
import asyncio as aio

@router.post("/automacao/executar")
async def automacao_executar(data: dict):
    login = ...; senha = ...; debug = ...
    loop = aio.get_running_loop()
    result = await loop.run_in_executor(
        None, executar_scraper, login, senha, debug
    )
    if "erro" in result:
        raise HTTPException(status_code=500, detail=result["erro"])
    return result
```

### 7.5 Download de arquivos (ex.: export XLSX/PDF)

Playwright captura o download por evento; salve em arquivo temporário, processe
e **sempre** delete no `finally`:

```python
import os, tempfile

async with report_page.expect_download(timeout=90000) as dl_info:
    await report_page.locator('a:has-text("Excel")').first.click()
download = await dl_info.value

tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
tmp_path = tmp.name
tmp.close()
try:
    await download.save_as(tmp_path)
    rows = parse_xlsx(tmp_path)   # openpyxl / xlrd / pandas
    return rows
finally:
    try:
        os.remove(tmp_path)
    except OSError:
        pass
```

### 7.6 Estratégias para sites legados (AngularJS etc.)

- **Esperas explícitas por seletor**, não `sleep` fixo quando possível:
  `await page.wait_for_selector('tr[ng-repeat*="..."]', timeout=20000)`.
- **Múltiplas estratégias**: tentar `page.evaluate(...)` (JS direto no DOM) e
  cair para locators Playwright como fallback.
- **Seleção por texto** quando o HTML é gerado e não tem id estável:
  `a:has-text("...")`, ou via JS localizando `anchor.textContent.trim() === ...`.
- **Componentes de dropdown customizados (ex.: selectize)** não são `<select>`
  nativo: clique no input visível e depois na opção:
  ```python
  await page.locator(".selectize-control .selectize-input").first.click()
  await page.locator('.selectize-dropdown .option', has_text="Relatório por cupom").first.click()
  ```
- **Abas novas**: após um clique que abre nova aba, pegue a última página do
  contexto: `pages = context.pages; nova = pages[-1]`, e feche-a ao terminar.
- **Campos mascarados**: use `input[ng-model*="..."]` e `input_value()` para
  ler valor já formatado.
- **Navegador visível para etapas manuais**: método aceita `debug=True`; para
  deixar aberto ao final, marque `self._keep_open = True` (o `__aexit__`
  respeita a flag e não fecha).

### 7.7 Scripts CLI para testar sem UI

Separe um script de linha de comando (`scripts/<scraper>.py`) que importa o
wrapper e roda fora do FastAPI — permite iterar nos seletores sem subir a app:

```python
import argparse, asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.modules.<slug>.automacao import executar_scraper

parser = argparse.ArgumentParser()
parser.add_argument("--login", required=True)
parser.add_argument("--senha", required=True)
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()
print(json.dumps(executar_scraper(args.login, args.senha, args.debug), ensure_ascii=False, indent=2))
```

### 7.8 Empacotamento e navegadores (atenção)

O PyInstaller **não inclui** os navegadores baixados pelo Playwright. A
estratégia do projeto é:

1. Tentar `channel="chrome"` (usa o **Chrome instalado** no sistema).
2. Fallback para o Chromium do Playwright (requer `playwright install chromium`).

Se quiser embarcar o navegador no executável, use
`PLAYWRIGHT_BROWSERS_PATH=0` no momento do build e colete o pacote via
`PyInstaller.utils.hooks.collect_data_files('playwright')` no `.spec`. Caso
contrário, trate o navegador como dependência externa (documente no instalador
ou baixe no primeiro uso).

---

## 8. Build e distribuição

### Comandos (Makefile)

| Alvo            | Ação                                                     |
|-----------------|----------------------------------------------------------|
| `make dev`      | FastAPI (8754, reload) + Vite (5173) em paralelo         |
| `make dev-api`  | Só FastAPI com reload                                     |
| `make dev-frontend` | Só Vite                                              |
| `make build`    | `build-frontend` + `build-bin`                          |
| `make build-frontend` | `npm install && npm run build` → `dist/`          |
| `make build-bin`| `pyinstaller <spec> --clean --noconfirm`                 |
| `make clean`    | Remove `build/`, `dist/`, `dist/`, caches                |
| `make install`  | `pip install -r requirements.txt` + `npm install`       |

### Spec do PyInstaller — pontos-chave

- `Analysis(['app/main.py'])`.
- `datas=[('app/frontend/dist', 'frontend/dist')]` — frontend embutido.
- `hiddenimports`: submódulos do uvicorn, `collect_submodules('app.modules')`,
  bibliotecas opcionais (ex.: `openpyxl`, `xlrd`, `reportlab...`) e os
  backends do pywebview por SO:
  - win32 → `webview.platforms.edgechromium`, `webview.platforms.winforms`, `clr`
  - darwin → `webview.platforms.cocoa`
  - linux → `webview.platforms.gtk`, `webview.platforms.qt`
- `excludes` para reduzir tamanho (`tkinter`, `numpy`, `pandas`, `matplotlib`).
- `console=False` (app sem terminal).
- No macOS, um `BUNDLE(...)` com `info_plist` gera o `.app`.

### Auto-update (opcional)

`core/updater.py` usa só a stdlib: consulta a API de *releases* do GitHub,
baixa o asset do SO atual, extrai se for `.zip` e troca o executável/`.app` em
um script de swap que relança a app. Expoe rotas `/api/update/{check,download,apply}`.

---

## 9. Receita para replicar a arquitetura

**Backend**
1. Crie `app/main.py` (thread da API + pywebview) e `app/api.py` (factory).
2. Crie `core/config.py` com `Settings` e resolução de `DATA_DIR` por SO/frozen.
3. Crie `core/logger.py`, `core/events.py`, `core/cache.py`,
   `core/permissions.py`, `core/utils.py`.
4. Crie `core/database.py` (ABC), `core/db_service.py` e
   `drivers/tinydb_driver.py`.
5. Crie `core/module_registry.py` (descoberta via `pkgutil`).
6. Crie `core/__init__.py` com `AppContext` singleton.
7. Em `api.py`: `discover()`, inclua os routers, rotas built-in e monte o
   `StaticFiles` do `dist/`.

**Módulo**
8. `app/modules/<slug>/manifest.py` + `__init__.py` com `router`.
9. Para automação: `automacao.py` com scraper async + wrapper síncrono.

**Frontend**
10. `npm create vite` (svelte-ts) + `@tailwindcss/vite`; configure alias `$lib`,
    proxy `/api`, `outDir=dist`.
11. `app.css` com `@import "tailwindcss"; @theme { ... }`.
12. `lib/router.svelte.ts` (hash router) e `lib/utils.ts` (`cn`).
13. `App.svelte` (shell + `loadModules` + blocos `{#if}` por rota).
14. Componentes de módulo em `src/modules/<slug>/`.
15. Rotas de automação chamam o wrapper via `run_in_executor`.

**Entrega**
16. `Makefile` (`dev`, `build`), `requirements.txt`, spec do PyInstaller com o
    `dist/` em `datas` e hiddenimports de uvicorn/pywebview.

### Checklist final

- [ ] `app_context` acessível e único.
- [ ] Dev grava em `app/data/`; frozen grava no dir do usuário.
- [ ] Módulo expõe `manifest` + `router`; é descoberto sem registro manual.
- [ ] Frontend usa hash router e `fetch` para `/api`.
- [ ] Automação roda fora do event loop (`run_in_executor`).
- [ ] Downloads usam tempfile e são deletados no `finally`.
- [ ] `dist/` embutido no executável via `.spec`.

---

## 10. Convenções

- **Core não importa módulo.** Módulos importam core.
- **Nada de regra de negócio no frontend.** Só renderização, interação e
  `fetch`.
- **Banco sempre via `app_context.database`.** Nunca importar o driver no
  módulo.
- **Comunicação entre módulos por eventos** (EventBus), evitando acoplamento.
- **Automação sempre com fallback** de navegador e de seletor, e retornando
  `{"erro": ...}` em vez de deixar exceção vazar para a rota.
- **`.svelte.ts` para estado reativo de vida longa** (cache entre montagens).
- **Svelte 5:** `{#if}` para componente dinâmico; nunca
  `<svelte:component this={...}>`.
