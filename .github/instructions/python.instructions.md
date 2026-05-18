---
applyTo: '**/*.py'
---

## 🛠️Coding Instructions for Python in This Repository

Follow these rules **strictly** when generating Python code:

### Python Version

* Use Python 3.13: Ensure all code uses features and syntax compatible with Python 3.13.
* Use PEP 695 `type` statement for type aliases: `type UserAccountSortableField = Literal["name", "email"]`
* Use PEP 695 generic class syntax where possible: `class EnvelopeE[ErrorT](BaseModel):`
* Use `X | None` union syntax (not `Optional[X]`)

### Type Annotations

* Always use full type annotations for all functions and class attributes.
* ❗ **Exception**: Do **not** add return type annotations in `test_*` functions.

### Documentation with Annotated Types

* Use `annotated_types.doc()` for parameter and return type documentation instead of traditional docstring Args/Returns sections
* **Apply documentation only for non-obvious parameters/returns**:
  - Document complex behaviors that can't be deduced from parameter name and type
  - Document validation rules, side effects, or special handling
  - Skip documentation for self-explanatory parameters (e.g., `engine: AsyncEngine`, `product_name: ProductName`)
* **Import**: Always add `from annotated_types import doc` when using documentation annotations

**Examples:**
```python
from typing import Annotated
from annotated_types import doc

async def process_users(
    engine: AsyncEngine,  # No doc needed - self-explanatory
    filter_statuses: Annotated[
        list[Status] | None,
        doc("Only returns users with these statuses")
    ] = None,
    limit: int = 50,  # No doc needed - obvious
) -> Annotated[
    tuple[list[dict], int],
    doc("(user records, total count)")
]:
    """Process users with filtering.

    Raises:
        ValueError: If no filters provided
    """
```

* **Docstring conventions**:
  - Keep docstrings **concise**, focusing on overall function purpose
  - Include `Raises:` section for exceptions
  - Avoid repeating information already captured in type annotations
  - Most information should be deducible from function name, parameter names, types, and annotations

### Code Style & Formatting

* Follow [Python Coding Conventions](../../docs/coding-conventions.md) **strictly**.
* Format code with `ruff`.
* Lint code with `ruff` and `pylint`.

### Library Compatibility

Ensure compatibility with the following library versions:

* `sqlalchemy` ≥ 2.x
* `pydantic` ≥ 2.x
* `fastapi` ≥ 0.100

### Code Practices

* Use `f-string` formatting for all string interpolation except for logging message strings.
* Prefer `f"{value}"` over `str(value)` for converting values to strings.
* Use **relative imports** within the same package/module.
  - For imports within the same repository/project, always use relative imports (e.g., `from ..constants import APP_SETTINGS_KEY` instead of `from simcore_service_webserver.constants import APP_SETTINGS_KEY`)
  - Use absolute imports only for external libraries and packages
* Place **all imports at the top** of the file.
* Document functions when the code is not self-explanatory or if asked explicitly.

### JSON Serialization

* Prefer `json_dumps` / `json_loads` from `common_library.json_serialization` instead of the built-in `json.dumps` / `json.loads`.
* When using Pydantic models, prefer methods like `model.model_dump_json()` for serialization.

### Controller-Service-Repository Architecture

This repository follows the **Controller-Service-Repository** layered design pattern. When adding or modifying features, respect these layers:

* **Controller**: Thin HTTP/REST handler. Parses requests, calls the service layer, and formats the response. Keep business logic **out** of controllers.
  - Controllers should delegate complex logic to the service layer rather than calling repositories or other services directly.
  - Example: `_controller/rest/accounts_rest.py` calls `_accounts_service.py`, never `_accounts_repository.py` directly.
* **Service**: Business logic and orchestration. Coordinates repositories, validates business rules, and calls other services.
  - Service functions accept `app: web.Application` (for aiohttp) or equivalent and use dependency injection to obtain engines/connections.
* **Repository**: Data access layer. In the case of services which have access to the database, contains all SQLAlchemy queries. Returns raw dicts or simple typed structures, not HTTP-aware types.
  - Access to other services (e.g., via HTTP clients or RPC clients) is also typically located in the repository layer, or occasionally in the service layer.

When refactoring, move business logic from controllers to services (e.g., extracting preview/notification logic into service functions like `preview_rejection_user_account`).

### Error Handling & Exceptions

* Define domain-specific exception hierarchies rooted in a base error per module:
  ```python
  class UsersBaseError(WebServerBaseError): ...
  class UserNotFoundError(UsersBaseError):
      msg_template = "User id {user_id} not found"
  ```
* Use `OsparcErrorMixin` from `common_library.errors_classes` for error classes that need structured context.
* Include `error_context()` data in exceptions for downstream handlers.
* Map exceptions to HTTP errors using `ExceptionToHttpErrorMap` dicts and `exception_handling_decorator`.
* Use `user_message(...)` from `common_library.user_messages` for all user-facing error/status strings. Include `_version=N` for versioning.
* Use `create_troubleshooting_log_kwargs(...)` from `common_library.logging.logging_errors` for structured error logging.
* Use `log_context(logger, level, msg)` from `servicelib.logging_utils` for scoped log blocks.

### Pydantic Models

* Use Pydantic v2 API exclusively:
  - `model_dump()` / `model_dump_json()` (not `.dict()` / `.json()`)
  - `model_validate()` (not `parse_obj()`)
  - `model_copy(update={...})` (not `.copy(update=...)`)
  - `model_config = ConfigDict(...)` (not inner `class Config`)
* Use `model_dump(exclude_none=True)` or `model_dump(by_alias=True, exclude_none=True)` when serializing for API responses with optional fields.
* Settings classes should use `create_from_envs()` classmethod pattern for environment-based construction.
* Organize model exports in `__init__.py` using `__all__: tuple[str, ...]` with sorted entries:
  ```python
  __all__: tuple[str, ...] = (
      "EmailAttachment",
      "EmailContact",
      "EmailContent",
  )
  ```

### SQLAlchemy Patterns

* **Prefer `EXISTS` over `JOIN` + `GROUP BY`** for access-rights and membership checks:
  ```python
  access_exists = sa.exists(
      sa.select(sa.literal(1)).where(
          (acl_table.c.resource_id == main_table.c.id)
          & (acl_table.c.read)
          & (acl_table.c.gid.in_(user_group_ids))
      )
  )
  query = sa.select(main_table).where(access_exists)
  ```
  EXISTS lets the planner stop at the first matching row and avoids materialising grouped results.
* **Prefer `NOT EXISTS` over `LEFT JOIN ... IS NULL`** for anti-join patterns.
* Comment complex SQL with rationale explaining **why** a particular query shape was chosen.
* Use `sa.literal(1)` in EXISTS subqueries (not `sa.literal(True)` or column selections).
* Use helper utilities like `create_ordering_clauses()` from `simcore_postgres_database.utils_ordering` for dynamic sort clauses.

### FastAPI Patterns

* Use **lifespan events** (via `LifespanManager` from `fastapi_lifespan_manager`) instead of deprecated `app.add_event_handler("startup"/"shutdown")`.
* Structure lifespans as `async def _my_lifespan(app: FastAPI) -> AsyncIterator[State]` functions that yield state dicts.
* Compose lifespans in a `create_app_lifespan(...)` factory function that adds them in order.
* Use `initialize_prometheus_instrumentation` (not `setup_prometheus_instrumentation`).

### aiohttp Framework

* **Application Keys**: Always use `web.AppKey` for type-safe application storage instead of string keys
  - Define keys with specific types: `APP_MY_KEY: Final = web.AppKey("APP_MY_KEY", MySpecificType)`
  - Use precise types instead of generic `object` when the actual type is known
  - Example: `APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)`
  - Store and retrieve: `app[APP_MY_KEY] = value` and `data = app[APP_MY_KEY]`
* **Request Keys**: Use `web.AppKey` for request storage as well for consistency and type safety
* **Middleware**: Follow the repository's middleware patterns for cross-cutting concerns
* **Error Handling**: Use the established exception handling decorators and patterns
* **Route Definitions**: Use `web.RouteTableDef()` and organize routes logically within modules

### Assertions & Safety Comments

* Prefer using logging over `print()` for runtime messages. Use `# noqa: T201` on intentional `print()` calls (e.g., startup/shutdown banners).
* Use `# type: ignore[assignment]` sparingly for legitimate Pydantic/typing workarounds, with context if non-obvious.

### Running tests
* Use `--keep-docker-up` flag when testing to keep docker containers up between sessions.
* Always activate the python virtual environment before running pytest.
