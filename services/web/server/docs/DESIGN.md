# Web-Server Architecture & Design Guidelines

> This document defines the **design decisions** and the **invariants/rules** to follow when
> working on the web-server. It is normative: code should conform to it.
>

---

## Overview

The web-server is a plugin-based [aiohttp](https://docs.aiohttp.org) application organized by
**domain**. Each domain (e.g. `users`, `groups`, `products`, `projects`) is a self-contained
folder that owns a cohesive piece of functionality and is structured in well-defined layers.

### Foundational decisions

- **aiohttp web app** assembled from plugins at startup.
- **CLI entrypoint** for running and managing the service.
- **One folder per domain**; the folder is the unit of ownership and isolation.
- **Per-domain Pydantic settings**, assembled into the application settings and **frozen** at app
  creation — configuration is immutable during request handling.
- **Plugin setup**: each domain configures itself via `plugin.py:setup_<domain>()`, which wires
  routes, middleware, and lifespan hooks based on its settings.
- **Layered domains**: a domain is split into controller, service, repository, and (when needed)
  external-interface layers, plus cross-domain aggregation and satellite services.

---

## Application Structure

```python
# application.py
def create_application(tracing_config) -> web.Application:
    app = create_safe_application()
    setup_settings(app)          # assemble + freeze settings
    # ... setup_<domain>(app) for each enabled plugin
    return app
```

**Rules**

- Settings are created and frozen once in `create_application()`; never mutate settings after startup.
- A domain is enabled/disabled through its settings field on `ApplicationSettings`.
- A plugin's `setup_<domain>()` is the only place that registers that domain's routes, middleware,
  and lifespan hooks.

---

## Domain Layer Model

Each domain folder follows this layout. Modules prefixed with `_` are **private** to the domain.

```
<domain>/
  _controller/
    rest.py                          # REST handlers: serve + translate models ONLY
    rpc.py                           # RPC handlers (optional)
  _service.py                        # private: the domain's business logic
  <domain>_service.py                # PUBLIC FACADE: re-exports service API via __all__
  _repository.py                     # private: data access (postgres/redis/rabbit)
  _<backend>_client.py               # private: I/O to an EXTERNAL service (http/rpc)
  _<feature>_aggregation_service.py  # private: cross-domain feature glue (this domain primary)
  _<other_domain>_service.py         # private: this domain's adapter to ANOTHER domain (satellite)
  _models.py                         # private: domain models (re-exported via facade)
  _errors.py                         # private: domain exceptions (re-exported via facade)
  settings.py                        # Pydantic settings for this domain
  plugin.py                          # setup_<domain>(): wiring
```

### Layer responsibilities and invariants

#### Controller (`_controller/rest.py`, `rpc.py`)
- **Responsibility:** serve a request and translate models (request → call → response).
- **Invariants:**
  - Contains no business logic. Orchestrating service calls *is* business logic and does not belong here.
  - Calls its own domain's service or an aggregation service; never a repository or client directly.
  - Maps domain models ⇄ transport schemas (REST/RPC).

#### Service (`_service.py` + public facade `<domain>_service.py`)
- **Responsibility:** the domain's business logic; orchestrates repository and client calls.
- **Invariants:**
  - `_service.py` holds the implementation; `<domain>_service.py` is a thin facade that re-exports
    the public functions with an explicit `__all__`.
  - Other domains call **only** the facade, never `_service.py` or other private modules.

#### Repository (`_repository.py`)
- **Responsibility:** data access to **owned** stores (postgres, redis, rabbit) for this domain.
- **Invariants:**
  - Pure persistence I/O; no cross-domain business logic.
  - Not imported from outside the domain.

#### Client / Gateway (`_<backend>_client.py`)
- **Responsibility:** I/O to an **external** backend (HTTP or RPC). The remote-service analog of the
  repository layer.
- **Invariants:**
  - Pure I/O: serialize the request, call the backend, map transport errors to domain errors.
  - No business logic. The service layer orchestrates repositories and clients together.
  - May be hidden behind an abstraction (ABC) to decouple higher-level modules when useful.

#### Aggregation service (`_<feature>_aggregation_service.py`)
- **Responsibility:** glue several domains together to implement **one feature** for a controller.
  Lives at the **domain level** of the **primary** domain (not inside `_controller/`).
- **Invariants:**
  - Imports other domains **only via their public facade**.
  - Contains orchestration, not persistence or transport logic.
  - Private by default; re-export from the facade only when reused by ≥2 consumers.
- **On coupling:** if A's aggregation imports B and C, only `A → B` and `A → C` are introduced.
  B and C do **not** import A and remain decoupled from each other. Exposing the feature in A's
  facade only makes *consumers of that feature* depend on A — its owner. The dependency graph must
  stay one-directional and acyclic: B or C must never import A's facade to reuse A's feature.

#### Satellite service (`_<other_domain>_service.py`)
- **Responsibility:** *this domain's adapter to another domain* — e.g. `projects/_tags_service.py`
  is projects' use of the tags domain.
- **Invariants:**
  - **Lives in the consuming domain** and stays co-located with its consumer.
  - Calls the other domain's **public facade**, passing scalar identifiers (IDs, names).
  - It is **not** moved into the other domain. Extraction is warranted only when *multiple* domains
    need *identical* cross-domain logic (rare).

### Aggregation vs Satellite (at a glance)

|            | Aggregation service                 | Satellite service                                    |
| ---------- | ----------------------------------- | ---------------------------------------------------- |
| Focus      | A feature for a controller          | This domain's use of another domain                  |
| Location   | Primary domain                      | Consuming domain                                     |
| Naming     | `_<feature>_aggregation_service.py` | `_<other_domain>_service.py`                         |
| Spans      | Several domains                     | One other domain                                     |
| Moves out? | No                                  | No (only if multiple consumers need identical logic) |

---

## Public Facade Rules

- The single public surface of a domain is `<domain>_service.py`.
- A `_` prefix marks a module as private to its domain — this applies to `_models.py` and
  `_errors.py` just as much as `_repository.py` or `_service.py`.
- Cross-domain imports go through `<domain>_service.py` only — functions, models, **and**
  exceptions alike. Never reach through to any `_`-prefixed module of another domain.
- Facades re-export with an explicit `__all__` and contain no implementation.

```python
# ✅ Correct — functions, models, and exceptions all via the facade
from ..users.users_service import get_users_in_group, UserID, UserNotFoundError
group_members = await get_users_in_group(app, gid=gid)

# ❌ Wrong — bypasses the facade, couples to internals
from ..users._users_repository import get_users_ids_in_group
from ..users._models import UserID          # _prefix = private
from ..users._errors import UserNotFoundError  # _prefix = private
```

---

## Cross-Domain Dependency Rules

- Depend on other domains **only through their public facades**.
- Pass **scalar identifiers** (IDs, names) across domain boundaries rather than another domain's
  model objects, where reasonable.
- Cross-domain orchestration belongs in an **aggregation service** (primary domain) or a
  **satellite service** (consuming domain) — never in a controller or a repository.
- The dependency direction must match ownership: a satellite adapter is a *thin* caller of another
  domain's facade; it must not manipulate the other domain's internal invariants.

---

## Settings & Plugin Setup Rules

- Each domain defines its settings in `settings.py`; they are assembled into `ApplicationSettings`
  and frozen at startup.
- A plugin declares its dependencies **explicitly**, by importing and calling the dependency's
  `setup_*()` at the start of its own `setup_<domain>()`.
- `@app_setup_func` / `ensure_single_setup` makes every `setup_*()` **idempotent** (runs at most
  once), so calling a dependency's setup from multiple plugins is safe.
- A plugin must therefore **not** rely on the order of setups in `create_application()` for
  correctness — each plugin pulls in what it needs itself. The dependency graph must be acyclic.
- This explicit import-and-call approach is the convention **until** we adopt a dependency-injection
  pattern that resolves and injects dependencies automatically.

```python
@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GROUPS",
)
def setup_groups(app: web.Application):
    # explicitly pull in dependencies; idempotent thanks to ensure_single_setup
    setup_products(app)
    setup_scicrunch(app)
    ...
```

---

## Testing Invariants

See [TESTS.md](./TESTS.md) for testing invariants and conventions.

---

## Known Design Debt

Flagged here so it is not forgotten; details and fixes are tracked in [MIGRATION.md](./MIGRATION.md).

- **`projects/` duplication** — orchestration logic duplicated between `projects/` adapters and
  other domains.
- **`projects/` inverted dependencies** — some `projects/_X_service.py` files manipulate domain X's
  internal invariants instead of acting as a thin adapter to X's facade. This is not fixed by
  renaming the file to `X/_projects_service.py` (that adapter points the opposite way, `X → projects`).
  The logic that protects X's invariants belongs **in X** (behind `x_service`); projects then calls
  it through the facade. Decide direction by: (1) who owns the invariants is the dependee;
  (2) the consumer holds the thin adapter; (3) keep the graph acyclic — foundational domains
  (e.g. tags, wallets) must not depend back on orchestration domains (e.g. projects).


IMPORTANT: ADD items above with newly found Design Issues and/or Gotchas
