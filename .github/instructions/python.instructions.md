---
applyTo: '**/*.py'
---

# Python instructions

Target the Python version in `.python-version`.

## Tooling

- Use `uv` (`uv pip install`, `uv run --with <pkg> <tool>`) and `make reqs`;
  never bare `pip` or `pip-compile`. See
  [Python Dependencies](../../requirements/python-dependencies.md).
- Run Ruff, Pylint, and mypy through repository commands or pre-commit; global
  tool configuration may differ from CI.

## Typing

- Use `X | None`, not `Optional[X]`.
- Use PEP 695 syntax for new type aliases and generics
  (`type SortField = Literal["name", "email"]`, `class EnvelopeE[ErrorT](BaseModel)`).
  Keep assignment-based aliases when the alias must be callable at runtime
  (e.g. `ProductName(...)`) or carries Pydantic metadata: a `type` statement is
  not callable and can alter generated schemas.
- Do not rewrite existing code solely to modernize syntax.
- Annotate public functions, methods, class attributes, and non-obvious values.

## Documentation

- Prefer clear names, types, and small functions over comments.
- Document only public or non-obvious behavior: contracts, side effects,
  invariants, concurrency constraints. Use `Raises:` only for domain exceptions
  callers must handle.
- Use `Annotated[..., doc(...)]` (`from annotated_types import doc`) for
  non-obvious parameter or return semantics.

## Imports and logging

- Follow [Python Coding Conventions](../../docs/coding-conventions.md).
- Import at module scope. Import locally only to avoid a verified cycle or defer
  an optional/expensive dependency, with a brief reason.
- Match the containing package's import style: relative within a package,
  absolute across package/service boundaries.
- Use f-strings, except in logging, which defers formatting:
  `logger.info("Processed %d users for %s", count, project_id)`.
- Use logging, not `print()`. If `print()` is unavoidable, add `# noqa: T201`
  and a reason.

## Retries and async file access

- Use the `tenacity` library wherever retries are needed. Do not hand-write
  retry loops with `sleep`. Reuse existing policies in
  `servicelib.retry_policies` before defining new ones.
- Bound every retry (`stop_after_attempt` or `stop_after_delay`), use
  `wait_exponential`/`wait_random_exponential` for remote calls, retry only
  specific exceptions (`retry_if_exception_type`), and log via
  `before_sleep_log`.
- Use `aiofiles` for file access inside `async` code instead of blocking
  `open()`/`Path.read_*()`/`write_*()` calls.

## Pydantic, serialization, and configuration

- Use Pydantic v2 APIs only (`model_dump`, `model_validate`, `model_copy`,
  `ConfigDict`). Use `model_dump_json()` only when a JSON payload is required.
- Use `common_library.json_serialization.json_dumps`/`json_loads` for project
  JSON payloads; never double-serialize framework responses.
- Keep credentials in `SecretStr`/`SecretBytes`; unwrap only at the boundary
  that needs the raw value and never log them.
- Follow the endpoint/event contract for omitting `None` (`exclude_none=True`)
  vs emitting `null`.
- Build env-backed settings with the local `create_from_envs()` pattern.
- Re-exported public model APIs use a typed, alphabetized
  `__all__: tuple[str, ...]`; do not add a re-export layer solely for this.

## HTTP-service architecture

Only when modifying HTTP service application code.

- Keep handlers thin: validate input, call the service layer, convert the
  result to a response.
- Put business rules and orchestration in services, and database access in
  repositories whose outputs are not HTTP-aware types.
- Keep outbound HTTP/RPC behind the service's existing client/gateway
  abstraction.
- Do not add layers to small local code solely to satisfy this pattern.

## Errors and user messages

Only for domain errors or text exposed to API clients or end users.

- Extend the existing domain exception hierarchy; do not create a new one for
  an isolated internal error.
- Use `OsparcErrorMixin`/`error_context()` for structured context, and map
  endpoint-facing exceptions with the service's `ExceptionToHttpErrorMap` and
  `exception_handling_decorator`.
- Use `user_message(...)` for end-user text ([translation
  pipeline](../../scripts/i18n/README.md)); copy `_version` usage from nearby
  calls. Keep stable error codes separate from display messages.
- Never localize logs, metrics, tracing attributes, identifiers, or
  developer-facing exception context.
- Use `create_troubleshooting_log_kwargs(...)` and `log_context(...)` where the
  service already does.

## SQLAlchemy

Only when writing or changing queries.

- Follow the package's session, transaction, and repository patterns.
- Use `EXISTS` (`sa.literal(1)` in the subquery) or `NOT EXISTS` for membership
  and access checks that need no related columns. Do not use `JOIN` +
  `GROUP BY` to dedupe an existence check.
- Comment non-obvious query shapes with their semantic or performance reason.
- Use `create_ordering_clauses()` for dynamic sorting where the package already
  does.

## FastAPI

Only when modifying application lifecycle or instrumentation code.

- Use lifespan management, not startup/shutdown event handlers.
- Compose with the service's `LifespanManager`/`create_app_lifespan(...)`,
  preserving acquisition and teardown order. Write lifecycle functions as
  `async def _my_lifespan(app: FastAPI) -> AsyncIterator[State]`.
- Use `initialize_prometheus_instrumentation`, not
  `setup_prometheus_instrumentation`.

## Suppressions

- Use `# type: ignore[code]` only for a narrow typing limitation, with the most
  specific code and a reason when non-obvious.
