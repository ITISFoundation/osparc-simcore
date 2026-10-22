---
applyTo: '**/*.py'
---

# Python instructions

Target the Python version in `.python-version`.

## Tooling

- Use `uv pip install`, `uv run --with <pkg> <tool>`, and `make reqs`.
  Never use bare `pip` or `pip-compile`. See
  [Python Dependencies](../../requirements/python-dependencies.md).
- Run Ruff, Pylint, and mypy through repository commands or pre-commit. Global
  tool configuration may differ from CI.
- Pylint is not a pre-commit hook; CI runs it via `make pylint`. After editing
  Python files, run `pylint --rcfile=.pylintrc <changed files>` before
  finishing: a line-level `# noqa` satisfies ruff only, and pylint needs a
  matching `# pylint: disable=` directive.

## Typing

- Use `X | None`, not `Optional[X]`.
- Use PEP 695 syntax for new type aliases and generics:
  `type SortField = Literal["name", "email"]`, `class EnvelopeE[ErrorT](BaseModel)`.
  Keep assignment-based aliases when the alias must be callable at runtime
  or carries Pydantic metadata. For example, `ProductName(...)` requires a
  callable alias. A `type` statement creates a non-callable alias and can alter
  generated schemas.
- Do not rewrite existing code solely to modernize syntax.
- Fully annotate parameters and return types of all functions and methods,
  including private helpers. Annotate class attributes and non-obvious values.
- Declare module-level constants as `NAME: Final[T] = value` with an explicit
  type, including private ones and constants in test modules. Document
  non-obvious constant rationale with `Final[Annotated[T, doc(...)]]` instead
  of a preceding comment. A module-level `ContextVar` counts as one: its name is
  never rebound even though its value changes per context, so declare it as
  `Final[Annotated[ContextVar[T], doc(...)]]`.

## Documentation

- Prefer clear names, types, and small functions over comments.
- Document only public or non-obvious behavior: contracts, side effects,
  invariants, concurrency constraints. Use `Raises:` only for domain exceptions
  callers must handle.
- Rationale for a function, fixture, or test belongs in its docstring, not in
  a `# NOTE:` comment.
- Do not narrate bug history or incident stories in inline comments; a single
  factual sentence about the constraint is enough.
- Use `Annotated[..., doc(...)]` for non-obvious parameter or return semantics.
  Import `doc` with `from annotated_types import doc`.

## Imports and logging

- Follow [Python Coding Conventions](../../docs/coding-conventions.md).
- Import at module scope. Import locally only to avoid a verified cycle or defer
  an optional or expensive dependency. Explain the reason briefly.
- Match the containing package's import style. Use relative imports within a
  package and absolute imports across packages or services.
- Use f-strings, except in logging, which defers formatting:
  `logger.info("Processed %d users for %s", count, project_id)`.
- Use logging, not `print()`. If `print()` is unavoidable, add `# noqa: T201`
  and a reason.

## Retries and async file access

- Use the `tenacity` library wherever retries are needed. Do not hand-write
  retry loops with `sleep`. Reuse existing policies in
  `servicelib.retry_policies` before defining new ones.
- Bound every retry with `stop_after_attempt` or `stop_after_delay`.
  Use `wait_exponential` or `wait_random_exponential` for remote calls.
  Retry only specific exceptions with `retry_if_exception_type`.
  Log retries with `before_sleep_log`.
- Use `aiofiles` for file access inside `async` code instead of blocking
  calls to `open()`, `Path.read_*()`, or `write_*()`.

## Pydantic, serialization, and configuration

- Use only Pydantic v2 APIs, such as `model_dump`, `model_validate`, `model_copy`,
  and `ConfigDict`.
- For JSON payloads, use `model_dump_json()` to serialize Pydantic models.
  Use `json_dumps` and `json_loads` from `common_library.json_serialization`
  for all other data. Never double-serialize framework responses.
- Keep credentials in `SecretStr` or `SecretBytes`. Unwrap them only where the
  code needs the raw value. Never log them.
- Use `exclude_none=True` to omit `None` fields only when the endpoint's OpenAPI
  schema or event schema marks the field as optional. Otherwise, emit `null`.
  If the schema is unclear, ask before choosing.
- Use the local `create_from_envs()` pattern for settings backed by environment
  variables.
- Re-exported public model APIs use a typed, alphabetized
  `__all__: tuple[str, ...]`. Do not add a re-export layer solely for this.

## HTTP-service architecture

These rules apply when modifying HTTP service application code.

- Limit handlers to validating input, calling the service layer, and converting
  the result to a response.
- Put business rules and orchestration in services, and database access in
  repositories whose outputs are not HTTP-aware types.
- Use the service's existing client or gateway for outbound HTTP and RPC calls.
- Do not add layers to small local code solely to satisfy this pattern.

## Errors and user messages

These rules apply to domain errors and text exposed to API clients or end users.

- Extend the existing domain exception hierarchy; do not create a new one for
  an isolated internal error.
- Use `OsparcErrorMixin` and `error_context()` for structured context.
  Map endpoint-facing exceptions with the service's `ExceptionToHttpErrorMap` and
  `exception_handling_decorator`.
- Use `user_message(...)` for end-user text. See the [translation
  pipeline](../../scripts/i18n/README.md). Copy `_version` usage from nearby
  calls. Keep stable error codes separate from display messages.
- Never localize logs, metrics, tracing attributes, identifiers, or
  developer-facing exception context.
- Use `create_troubleshooting_log_kwargs(...)` and `log_context(...)` where the
  service already does.

## SQLAlchemy

These rules apply when writing or changing queries.

- Follow the package's session, transaction, and repository patterns.
- Use `EXISTS` or `NOT EXISTS` for membership and access checks that need no
  related columns. Use `sa.literal(1)` in the subquery. Do not combine `JOIN`
  and `GROUP BY` to remove duplicates in an existence check.
- Comment non-obvious query shapes with their semantic or performance reason.
- Use `create_ordering_clauses()` for dynamic sorting where the package already
  does.

## FastAPI

These rules apply when modifying application lifecycle or instrumentation code.

- Use lifespan management, not startup or shutdown event handlers.
- Compose lifespans with the service's `LifespanManager` and
  `create_app_lifespan(...)`. Preserve acquisition and teardown order.
  Write lifecycle functions as
  `async def _my_lifespan(app: FastAPI) -> AsyncIterator[State]`.
- Use `initialize_prometheus_instrumentation`, not
  `setup_prometheus_instrumentation`.

## Suppressions

- Use `# type: ignore[code]` only for a narrow typing limitation, with the most
  specific code and a reason when non-obvious.
