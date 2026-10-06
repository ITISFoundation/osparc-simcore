---
applyTo: '**/*.py'
---

# Python instructions

Target Python 3.13 as specified by `.python-version`. Follow the closest
applicable service- or package-level instructions in addition to this file.
For test files, also follow `python-tests.instructions.md`.

## Environment and dependency tooling

- Use `uv` for Python environment and dependency operations, not bare `pip`
  or `pip-tools`:
  - Install requirements with `uv pip install -r requirements/<file>.txt`
    (prefer installing a library with `uv pip install .`).
  - Compile `*.in` to `*.txt` with `uv pip compile`, via the repository
    workflow (`make reqs`), not `pip-compile`.
  - Run one-off tools with `uv run` (e.g. `uv run --with <pkg> <tool>`).
- Follow [Python Dependencies](../../requirements/python-dependencies.md) for
  the full workflow and [Environment Variables Guide](../../docs/env-vars.md)
  for configuration.

## Typing and language features

- Use Python 3.13-compatible syntax and standard-library APIs.
- For new type aliases, use PEP 695 syntax:
  ```python
  type UserAccountSortableField = Literal["name", "email"]
  ```
  Exceptions: keep assignment-based aliases (`TypeAlias` or `NewType`-style)
  when the alias must remain callable at runtime (e.g. `ProductName(...)` in
  `packages/pytest-simcore/src/pytest_simcore/faker_products_data.py`) or when
  it carries runtime metadata that a conversion would change (e.g. the
  Pydantic-annotated `DownloadLink` alias in
  `services/api-server/src/simcore_service_api_server/models/schemas/studies.py`).
  A PEP 695 `type` statement is not callable and can alter generated schemas.
- For new generic classes, prefer PEP 695 syntax when it is clearer and
  compatible with the repository's type-checking and runtime dependencies:
  ```python
  class EnvelopeE[ErrorT](BaseModel): ...
  ```
  Do not rewrite existing generic code solely to modernize syntax.
- Use `X | None`, not `Optional[X]`.
- Add explicit annotations to public functions, methods, class attributes, and
  non-obvious values. Follow existing local conventions for framework hooks,
  overloads, and dynamically typed boundaries.
- Test functions named `test_*` must not have a return type annotation. See
  `python-tests.instructions.md` for other test conventions.

## Documentation

- Prefer accurate names, types, and small functions over comments that repeat
  the implementation.
- Add concise documentation for public or non-obvious behavior, especially
  externally visible contracts, important side effects, invariants, ownership,
  concurrency constraints, and caller-relevant exceptions.
- Use `Annotated[..., doc(...)]` with `from annotated_types import doc` for
  non-obvious parameter or return semantics when that metadata is meaningful to
  the affected code or tooling.
- Do not document information already clear from the function name, parameter
  name, type, or surrounding code.
- Use a `Raises:` section only for expected, domain-relevant exceptions that
  callers need to handle or understand.

## Imports, formatting, and logging

- Follow [Python Coding Conventions](../../docs/coding-conventions.md) and the
  repository's configured Ruff, Pylint, and type-checking rules.
- Use repository-provided commands, pre-commit, or task-runner targets rather
  than assuming global tool configuration matches CI.
- Let configured tooling order imports. Do not manually fight formatter or
  import-sorter output.
- Place ordinary imports at module scope. Use a local import only to avoid a
  verified import cycle, defer an optional/expensive dependency, or support a
  runtime-only/platform-specific path. Add a brief rationale when it is not
  obvious.
- Follow the import convention used by the containing package. Relative imports
  are appropriate within a package when they match local code; use absolute
  imports for third-party packages and across independent package/service
  boundaries.
- Use f-strings for non-logging string interpolation.
- Use parameterized logging messages so formatting is deferred:
  ```python
  logger.info("Processed %d users for project %s", user_count, project_id)
  ```
- Prefer logging over `print()` for runtime output. Mark intentional `print()`
  calls with `# noqa: T201` where required by Ruff. Add a brief comment explaining why the `print()` is necessary.

## Serialization, configuration, and Pydantic

- Use `common_library.json_serialization.json_dumps` and `json_loads` for
  project-managed JSON payloads when their extended serialization behavior is
  needed. Do not double-serialize framework responses.
- For Pydantic v2 models, use `model_dump()` for Python data and
  `model_dump_json()` only when an actual JSON payload is required.
- Use Pydantic v2 APIs only:
  - `model_dump()` / `model_dump_json()`, not `.dict()` / `.json()`
  - `model_validate()`, not `parse_obj()`
  - `model_copy(update=...)`, not `.copy(update=...)`
  - `model_config = ConfigDict(...)`, not an inner `Config` class
- Represent credentials and other secrets using `SecretStr`, `SecretBytes`, or
  a more appropriate secret type. Unwrap a secret only at the boundary that
  requires its raw value; never log or expose it.
- Follow the endpoint/event contract when deciding whether `None` should be
  omitted (`exclude_none=True`) or represented as JSON `null`.
- For environment-backed settings, follow the local
  `create_from_envs()` construction pattern.
- When a package deliberately re-exports its public model API, use a typed,
  alphabetized `__all__: tuple[str, ...]`. Do not create a re-export layer
  solely for this convention.

## HTTP-service architecture

Apply this section only when modifying application code in an HTTP service.

- Keep controllers and request handlers thin: parse/validate transport input,
  call the service layer, and convert results to transport responses.
- Put business rules and orchestration in services.
- Put SQLAlchemy/database access in repositories. Repository outputs must not
  be HTTP-aware types.
- Keep outbound HTTP/RPC integration behind the service's established
  client/gateway/repository abstraction; do not embed it in controllers.
- Follow the existing service architecture. Do not introduce layers into small
  local code solely to satisfy this pattern.

## Errors and end-user messages

Apply this section only to domain errors or messages exposed to endpoint/API
clients or end users.

- Extend an existing module-level domain exception hierarchy when one exists;
  do not introduce a new hierarchy for an isolated implementation error.
- Use `OsparcErrorMixin` and `error_context()` when the established error
  handling flow requires structured context.
- Map endpoint-facing exceptions through the service's existing
  `ExceptionToHttpErrorMap` and `exception_handling_decorator` conventions.
- Use `user_message(...)` for localizable display text. Keep stable,
  machine-readable error codes separate from localized messages.
- Use `_version` according to nearby `user_message(...)` calls and the
  translation pipeline; do not invent versioning semantics.
- Do not localize logs, metrics, tracing attributes, identifiers, internal
  diagnostics, or developer-oriented exception context.
- Use `create_troubleshooting_log_kwargs(...)` and `log_context(...)` where
  the containing service already uses those structured logging conventions.

## SQLAlchemy

Apply this section only when writing or changing SQLAlchemy queries.

- Follow the package's existing session, transaction, and repository patterns.
- For boolean membership or access-control checks where no related-table
  columns are needed, prefer `EXISTS`; use `sa.literal(1)` in the subquery.
- For anti-membership checks, prefer `NOT EXISTS` when it expresses the intent
  clearly.
- Use joins when related data is needed, the existing query is clearer, or a
  measured query plan indicates that shape is preferable. Do not use
  `JOIN` + `GROUP BY` solely to compensate for duplicate rows from an existence
  check.
- Comment non-obvious query shapes with the semantic or performance rationale.
- Use repository helpers such as `create_ordering_clauses()` for dynamic sort
  clauses when the affected package already uses them.

## FastAPI

Apply this section only when modifying FastAPI application lifecycle or
instrumentation code.

- Prefer lifespan management over deprecated startup/shutdown event handlers.
- Follow the service's existing `LifespanManager` and
  `create_app_lifespan(...)` composition pattern. Preserve intentional resource
  acquisition and teardown order.
- Structure lifecycle functions consistently with local code, typically as
  `async def _my_lifespan(app: FastAPI) -> AsyncIterator[State]`.
- Use `initialize_prometheus_instrumentation`, not
  `setup_prometheus_instrumentation`.

## aiohttp

Apply this section only when modifying aiohttp application, request, middleware,
or routing code.

- Use typed `web.AppKey` objects rather than string keys for application and
  request storage:
  ```python
  APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)
  ```
- Use the most precise key type available; avoid `object` when a concrete type
  is known.
- Follow the affected service's established middleware, routing, and
  exception-handling patterns. Use `web.RouteTableDef()` where that is the
  local route-definition convention.

## Ordering and suppressions

- Keep `__all__` and clearly unordered, hand-maintained Python registries or
  mappings alphabetized when order has no runtime, API, or readability meaning.
- Preserve order that represents precedence, fallback, registration,
  initialization, execution, serialization, migration, dependency, or
  deliberate domain grouping.
- Do not make unrelated reorder-only changes.
- Use `# type: ignore[...]` only for a legitimate, narrow typing limitation.
  Prefer the most specific error code and explain a non-obvious suppression.

## Localization

- Use `user_message()` for end-user text, following the
  [translation pipeline guide](../../scripts/i18n/README.md).
- Keep stable programmatic error codes separate from localized display messages.
- Do not localize logs, metrics, internal diagnostics, identifiers, or
  developer-facing exception details unless a service-specific convention requires it.
