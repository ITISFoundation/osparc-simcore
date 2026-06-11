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
  <other_domain>_service.py          # PUBLIC: this domain's reusable adapter to ANOTHER domain (satellite)
  models.py                          # PUBLIC: domain models — pure type definitions, no service imports
  errors.py                          # PUBLIC: domain exceptions — pure definitions, no service imports
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
    the public **functions only** with an explicit `__all__`. It does **not** re-export models or exceptions
    — those are imported from `models.py` and `errors.py` directly by consumers.
  - Other domains call the service facade for functions: `await users_service.create_user(...)`; they
    import exceptions and types directly from their dedicated modules: `from ..users.errors import UserNotFoundError`
    and `from ..users.models import UserID`.
  - Example:
    ```python
    # ✅ Correct: import functions from service, types/exceptions from dedicated modules
    from ..users import users_service
    from ..users.models import UserID
    from ..users.errors import UserNotFoundError

    user_id: UserID = 123
    try:
        user = await users_service.get_user(app, user_id=user_id)
    except UserNotFoundError:
        pass

    # ✅ Correct: users_service.py exports only functions
    # users_service.py: __all__ = ("create_user", "get_user", "delete_user")

    # ❌ Wrong: importing types/exceptions from service facade
    from ..users.users_service import UserID, UserNotFoundError
    ```

#### Models (`models.py`) and Errors (`errors.py`)
- **Responsibility:** pure type and exception definitions owned by this domain.
- **Invariants:**
  - **Leaf modules** — they contain only class/type definitions and never import from any module
    within the web-server service layer (`_service.py`, `<domain>_service.py`, `_repository.py`,
    `_controller/`, any satellite, or any aggregation service).
  - May import from: stdlib, pydantic, external packages, and **other domains' `models.py` or
    `errors.py`** (leaf-to-leaf imports — always cycle-safe because both sides are leaves).
  - Export via `__all__`. Groups in `__all__` separated by comments (e.g. `# models`, `# exceptions`).
  - **This purity is what makes them safe to import from anywhere without creating cycles** — not
    namespace syntax. A `from ..users import errors` import still executes `errors.py`; the reason
    it cannot create a cycle is that `errors.py` has no outgoing imports into the service graph.

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
  - Imports other domains **only via their public surfaces** (`<domain>_service`, `models`, `errors`, or satellites).
  - Contains orchestration, not persistence or transport logic.
  - Private by default; re-export from the facade only when reused by ≥2 consumers.
- **On coupling:** if A's aggregation imports B and C, only `A → B` and `A → C` are introduced.
  B and C do **not** import A and remain decoupled from each other. Exposing the feature in A's
  facade only makes *consumers of that feature* depend on A — its owner. The dependency graph must
  stay one-directional and acyclic: B or C must never import A's facade to reuse A's feature.

#### Satellite service (`<other_domain>_service.py`)
- **Responsibility:** *this domain's reusable adapter to another domain* — e.g. `projects/tags_service.py`
  is projects' encapsulation of how it uses the tags domain.
- **Invariants:**
  - **Lives in the consuming domain** and stays co-located with its consumers.
  - Calls the other domain's **public surfaces** (`<domain>_service`, `models`, or `errors`), passing scalar identifiers (IDs, names).
  - **Public by default** (no `_` prefix): other domains or controllers *may* import and reuse it
    to avoid duplicating the same cross-domain adapter logic. This reduces coupling and centralizes
    the adapter pattern.
  - It is **not** moved into the other domain. Extraction into a shared location is warranted only
    when the logic becomes truly generic (rare).

### Aggregation vs Satellite (at a glance)

|            | Aggregation service                 | Satellite service                                                               |
| ---------- | ----------------------------------- | ------------------------------------------------------------------------------- |
| Focus      | A feature for a controller          | This domain's reusable adapter to another domain                                |
| Location   | Primary domain                      | Consuming domain                                                                |
| Naming     | `_<feature>_aggregation_service.py` | `<other_domain>_service.py` (public, no `_` prefix)                             |
| Spans      | Several domains                     | One other domain                                                                |
| Reusable?  | No (private to primary domain)      | Yes (other domains may import to reuse the pattern)                             |
| Moves out? | No                                  | No (stays in consuming domain, or extracted to shared package if truly generic) |

---

## Public Facade Rules

- **All public surfaces are imported as namespaces** (modules, not individual names) to avoid cycles and clarify intent.
- The **primary public surface** of a domain is `<domain>_service.py` — import via `from ..users import users_service`.
- **Secondary public surfaces** are:
  - **Satellite adapters:** `<other_domain>_service.py` (no `_` prefix) — import via `from ..projects import tags_service`
  - **Types & Exceptions:** `models.py` and `errors.py` (no `_` prefix, fully public) — import via `from ..users import models, errors`
- A `_` prefix marks a module as **private** — applies to `_repository.py`, `_service.py`, `_<feature>_aggregation_service.py`. Never import these from other domains.
- **Satellite name collision:** a satellite `<other_domain>_service.py` has the same module name as the primary facade it wraps (e.g., `projects/tags_service.py` and `tags/tags_service.py` both import as `tags_service`). When both are needed in the same file, alias the **satellite** with the consuming domain as prefix:
  ```python
  from ..tags import tags_service                              # primary facade
  from ..projects import tags_service as project_tags_service  # satellite (consuming domain = projects)
  ```
- Public modules export via an explicit `__all__` with no implementation.
- `__all__` groups: `<domain>_service.py` uses `# functions`; `models.py` uses `# models`; `errors.py` uses `# exceptions`.
- `__all__` entries must be **sorted alphabetically within each group**, with groups separated by comments.

```python
# ✅ Correct — namespace imports for services/satellites, direct imports for types and exceptions
from ..users import users_service           # service: namespace import
from ..projects import tags_service         # satellite in projects domain: namespace import
from ..users.models import UserID           # type: direct name import
from ..users.errors import UserNotFoundError  # exception: direct name import

# ✅ When a satellite name collides with the primary facade it wraps, alias the satellite:
from ..tags import tags_service                              # primary facade of tags domain
from ..projects import tags_service as project_tags_service  # satellite — alias with consuming domain prefix

user_id: UserID = 123
await users_service.get_users_in_group(app, gid=gid)
tags = await tags_service.get_project_tags(app, project_id=pid)
try:
    await users_service.create_user(app, name="Alice")
except UserNotFoundError:
    pass

# ❌ Wrong — wrong surface, private modules, or mixed-up style
from ..users.users_service import get_users_in_group  # avoid name import from service facade
from ..users._users_repository import get_users_ids_in_group  # _prefix = private
from ..users._errors import UserNotFoundError          # should be errors.py (no _)
from ..projects._tags_service import get_tags          # _prefix = private
```

---

## Cross-Domain Dependency Rules

- Depend on other domains **only through their public surfaces**.
- Pass **scalar identifiers** (IDs, names) across domain boundaries rather than another domain's
  model objects, where reasonable.
- Cross-domain orchestration belongs in an **aggregation service** (primary domain) or a
  **satellite service** (consuming domain) — never in a controller or a repository.
- The dependency direction must match ownership: a satellite adapter is a *thin* caller of another
  domain's facade; it must not manipulate the other domain's internal invariants.

### Preventing Cyclic Imports — Pure Leaf Modules + Three Public Surfaces

**Cyclic imports are forbidden** — the dependency graph must be acyclic (DAG). The design prevents
cycles structurally, not syntactically:

- **What actually prevents cycles:** `errors.py` and `models.py` are **pure leaf modules** — they
  have no outgoing imports into the service graph. A module with no service imports cannot complete
  a cycle chain. This is an invariant enforced by the design (see "Models and Errors" above).

- **Example: users ↔ user_preferences cycle is prevented by design:**
  ```python
  # ✅ user_preferences imports only the leaf errors module — no cycle possible
  from ..users.errors import FrontendUserPreferenceIsNotDefinedError
  raise FrontendUserPreferenceIsNotDefinedError("...")

  # ❌ importing users_service would pull in _service.py transitively — cycle risk
  from ..users.users_service import FrontendUserPreferenceIsNotDefinedError
  ```

- **Example: payments ↔ wallets cycle is prevented by design:**
  ```python
  # ✅ wallets imports only from the leaf errors module — no cycle possible
  from ..payments.errors import PaymentApiError

  # ❌ importing payments_service creates a cycle via payments._handlers → wallets
  from ..payments.payments_service import PaymentApiError
  ```

- **If a cycle is still detected** (e.g., an `errors.py` imported a service module by mistake):
  - Do not suppress with `# pylint: disable=cyclic-import`
  - Immediately restore the purity of `errors.py`/`models.py` (remove the offending service import)
  - If the import is genuinely needed at runtime, use one of the remediation strategies below

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

## Cyclic Import Remediation

These strategies apply when a cycle exists that **cannot** be resolved by the three-surface design
(e.g., two services need each other's runtime behaviour, not just types). Ordered by preference:

### 1. Restore Module Purity (Almost Always Correct)
- Check whether the cycle passes through `errors.py` or `models.py` that imported a service module.
  If so, remove the service import from the leaf module — this is a design rule violation to fix.
- Check whether the service facade (`<domain>_service.py`) is being imported only for a type or
  exception. If so, move that symbol to `errors.py` or `models.py` and import from there.
- **Benefit:** Fixes root cause; no new abstractions needed.

### 2. Use TYPE_CHECKING Guard (For Type Hints Only)
- If cycle involves only type annotations, wrap imports in `if TYPE_CHECKING:` block.
- **Example:** `from typing import TYPE_CHECKING; if TYPE_CHECKING: from ..other_domain import SomeType`
- **Benefit:** Type hints available to editor/mypy; no runtime import.

### 3. Lazy Imports (Temporary Only)
- If a genuine runtime mutual dependency exists, defer import to function body: `from ..other import x  # noqa: PLC0415`
- **Must:** Document in "Known Design Debt" why the cycle cannot be resolved with strategies 1–2.
- **Drawback:** Masks the structural problem; requires a proper fix within one sprint.

---

## Testing Invariants

See [TESTS.md](./TESTS.md) for testing invariants and conventions.
