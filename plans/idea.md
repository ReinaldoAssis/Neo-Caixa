# Arquitetura Base da Plataforma

> Documento de arquitetura para aplicações desktop modernas utilizando **Python + FastAPI + pywebview + Svelte**.

---

# Objetivos

Este projeto tem como objetivo criar uma plataforma para desenvolvimento de aplicações desktop modernas que combine as vantagens do ecossistema Python com a experiência de usuário das tecnologias Web.

A arquitetura foi projetada seguindo alguns princípios fundamentais:

- Excelente experiência de usuário (UX)
- Interface moderna
- Modularidade extrema
- Fácil manutenção
- Alta extensibilidade
- Baixo acoplamento
- Independência de banco de dados
- Possibilidade de reutilização dos módulos em outros projetos

A filosofia do projeto é que **quase tudo seja um módulo**.

O núcleo da aplicação deve ser pequeno e responsável apenas por fornecer serviços básicos para os módulos.

---

# Stack Tecnológica

## Backend

- Python 3.13+
- FastAPI
- Uvicorn

## Frontend

- Svelte
- Vite
- TypeScript
- shadcn-svelte
- TailwindCSS

## Desktop

- pywebview

## Banco de Dados

Inicialmente:

- TinyDB

No futuro poderá ser substituído por:

- SQLite
- PostgreSQL
- MySQL
- MongoDB
- Redis
- qualquer outro banco

Sem necessidade de alterar os módulos.

---

# Arquitetura Geral

```
                ┌─────────────────────────────┐
                │        pywebview            │
                │  Janela Desktop Nativa      │
                └──────────────┬──────────────┘
                               │
                     http://localhost
                               │
             ┌─────────────────▼─────────────────┐
             │             FastAPI               │
             │                                   │
             │ REST API                          │
             │ WebSocket                         │
             │ Sistema de Plugins                │
             └──────────────┬────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
     Core Module       Plugins           Database Driver

                            │
                            ▼

                    TinyDB / SQLite /
                  PostgreSQL / etc...
```

---

# Organização do Projeto

```
app/

    main.py

    core/
    modules/

    frontend/

        src/
        static/
        components/
        routes/

    assets/

```

---

# O Core

O diretório **core** representa o coração da aplicação.

Ele deve conter apenas funcionalidades fundamentais que serão utilizadas por todos os módulos.

O Core **não deve conhecer nenhum módulo**.

O fluxo de dependências deve sempre apontar para o Core.

```
Módulo A
          \
Módulo B -----> Core
          /
Módulo C
```

Nunca:

```
Core
   ↓
Módulo
```

---

# Responsabilidades do Core

O Core deverá fornecer serviços compartilhados, como:

- Sistema de banco de dados
- Configuração
- Registro de módulos
- Sistema de eventos
- Logger
- Sistema de permissões
- Serviços compartilhados
- Gerenciamento de cache
- Utilidades

---

# Arquitetura Modular

Toda funcionalidade da aplicação deverá ser implementada através de módulos.

Exemplos:

```
Dashboard

Financeiro

Estoque

Relatórios

Usuários

Agenda

Clientes

Produtos

Notas
```

Cada módulo deve ser autocontido.

Idealmente, remover uma pasta de módulo deve remover completamente aquela funcionalidade da aplicação.

---

# Estrutura de um Módulo

Exemplo de estrutura de um módulo:
```
financeiro/

    api.py

    service.py

    repository.py

    models.py

    views.py

    permissions.py

    routes.py

    frontend/

        pages/

        components/

    assets/

    manifest.py
```

Cada módulo será responsável por:

- sua API
- suas regras de negócio
- suas telas
- seus componentes
- suas permissões
- seus modelos

---

# Comunicação Backend ↔ Frontend

Toda comunicação será realizada através da API HTTP do FastAPI.

```
Svelte

↓

fetch()

↓

FastAPI

↓

Serviços

↓

Banco
```

Para atualizações em tempo real será utilizado WebSocket.

```
Python

↓

WebSocket

↓

Svelte
```

Nenhuma lógica de negócio deverá existir no frontend.

---

# Frontend

O frontend será uma SPA construída em Svelte.

A interface utilizará:

- shadcn-svelte
- TailwindCSS

A UI deverá ser responsável apenas por:

- renderização
- interação do usuário
- chamadas para API
- gerenciamento de estado da interface

Toda regra de negócio pertence ao backend.

---

# Componentização

Toda interface deverá ser construída utilizando componentes reutilizáveis.

Exemplo:

```
Button

Dialog

Table

CrudTable

Sidebar

Navbar

Card

Charts

Forms
```

Sempre que possível evitar duplicação de código.

---

# Banco de Dados

O projeto deve ser completamente agnóstico ao banco utilizado.

Nenhum módulo poderá acessar diretamente TinyDB, SQLite ou qualquer outro banco.

Todos deverão utilizar apenas a interface definida pelo Core.

Exemplo:

```
Módulo

↓

Database Service

↓

Driver

↓

TinyDB
```

No futuro:

```
Módulo

↓

Database Service

↓

Driver

↓

PostgreSQL
```

O módulo não deverá sofrer nenhuma alteração.

---

# Camada de Banco

O Core disponibilizará uma interface abstrata para persistência.

Exemplo conceitual:

```
Database

├── insert()

├── update()

├── delete()

├── get()

├── search()

└── transaction()
```

Cada implementação concreta ficará em um driver separado.

```
drivers/

    tinydb.py

    sqlite.py

    postgres.py
```

---

# Serviços

A lógica de negócio deverá ficar concentrada em Services.

```
API

↓

Service

↓

Repository

↓

Database
```

Isso facilita:

- testes
- manutenção
- reutilização

---

# Sistema de Eventos

Os módulos deverão se comunicar preferencialmente através de eventos.

Exemplo:

```
Pedido criado

↓

Evento

↓

Financeiro

↓

Estoque

↓

Notificações
```

Os módulos não precisam conhecer uns aos outros.

Isso reduz acoplamento.

---

# Registro de Módulos

Cada módulo possuirá um manifesto.

Exemplo:

```
manifest.py

Nome

Versão

Dependências

Menus

Rotas

Permissões

Eventos
```

O Core será responsável por descobrir e registrar automaticamente todos os módulos disponíveis.

---

# API

A API seguirá convenções REST.

```
GET

POST

PUT

DELETE
```

Para operações em tempo real:

- WebSocket

---

# Desenvolvimento do Frontend

Durante o desenvolvimento:

```
Svelte Dev Server

↓

FastAPI

↓

Hot Reload
```

Na produção:

```
Build Svelte

↓

Arquivos estáticos

↓

FastAPI

↓

pywebview
```

Assim não existe dependência de Node.js em produção.

---

# Empacotamento

A distribuição da aplicação será composta por um único executável.

Fluxo:

```
Python

+

FastAPI

+

Frontend Build

+

Assets

↓

PyInstaller

↓

Aplicação Desktop
```

O usuário final não precisará instalar:

- Python
- Node
- Navegador
- Dependências

---

# Filosofia da Arquitetura

Esta arquitetura foi construída sobre alguns princípios simples:

- O Core deve permanecer pequeno.
- Toda funcionalidade deve ser implementada em módulos.
- O frontend não contém regras de negócio.
- Os módulos não conhecem a implementação do banco de dados.
- O banco pode ser substituído sem alterar os módulos.
- Os módulos devem ser autocontidos.
- A comunicação entre módulos deve ocorrer preferencialmente por eventos.
- O sistema deve ser facilmente extensível.
- A experiência do usuário deve ter prioridade sobre decisões de implementação.
- A arquitetura deve favorecer simplicidade, manutenção e reutilização de código.