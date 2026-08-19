# Reusable Async PostgreSQL Unit of Work

## Status

Design proposal. No production code has been changed.

## Motivation

Several sequential repository calls currently acquire separate SQLAlchemy connections. Each call can incur pool checkout, `pool_pre_ping`, implicit transaction setup, and cleanup overhead.

A Unit of Work (UoW) lets a short group of database operations share one connection. For writes, it can also define one transaction boundary.

The generic lifecycle should live in `servicelib`, not be copied into every service. Each service supplies its own typed repository bundle and construction function.

A UoW is local to one service and one database engine. It is not a distributed transaction across services, RPC calls, or databases.

## Design Principles

- Acquire a connection only around contiguous database work.
- Do not hold connections during RPC calls, sleeps, retries, or CPU-intensive work.
- Keep repository bundles service-specific and statically typed.
- Preserve standalone repository use outside a UoW.
- Put connection and transaction lifecycle behavior in `servicelib`.
- Select read or transactional behavior explicitly.
- Treat the UoW as owner of its connection and outer transaction.

## Shared `servicelib` Implementation

The generic UoW accepts a service-specific repository builder. The builder receives the engine and active connection and returns a typed repository bundle.

```python
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


type RepositoryBuilder[RepositoriesT] = Callable[
    [AsyncEngine, AsyncConnection],
    RepositoriesT,
]


class AsyncpgUnitOfWork[RepositoriesT]:
    def __init__(
        self,
        engine: AsyncEngine,
        repository_builder: RepositoryBuilder[RepositoriesT],
        *,
        transactional: bool,
    ) -> None:
        self._engine = engine
        self._repository_builder = repository_builder
        self._transactional = transactional
        self._connection_context: AbstractAsyncContextManager[AsyncConnection] | None = None
        self.connection: AsyncConnection | None = None
        self.repositories: RepositoriesT

    async def __aenter__(self) -> Self:
        if self.connection is not None:
            msg = "Unit of work is already active"
            raise RuntimeError(msg)

        self._connection_context = (
            self._engine.begin()
            if self._transactional
            else self._engine.connect()
        )
        self.connection = await self._connection_context.__aenter__()

        try:
            self.repositories = self._repository_builder(
                self._engine,
                self.connection,
            )
        except BaseException as exception:
            # __aexit__ is not called when __aenter__ fails.
            await self._connection_context.__aexit__(
                type(exception),
                exception,
                exception.__traceback__,
            )
            self.connection = None
            self._connection_context = None
            raise

        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._connection_context is None:
            msg = "Unit of work is not active"
            raise RuntimeError(msg)

        try:
            return await self._connection_context.__aexit__(
                exception_type,
                exception,
                traceback,
            )
        finally:
            self.connection = None
            self._connection_context = None


@dataclass(frozen=True)
class AsyncpgUnitOfWorkFactory[RepositoriesT]:
    engine: AsyncEngine
    repository_builder: RepositoryBuilder[RepositoriesT]

    def read(self) -> AsyncpgUnitOfWork[RepositoriesT]:
        return AsyncpgUnitOfWork(
            self.engine,
            self.repository_builder,
            transactional=False,
        )

    def transaction(self) -> AsyncpgUnitOfWork[RepositoriesT]:
        return AsyncpgUnitOfWork(
            self.engine,
            self.repository_builder,
            transactional=True,
        )
```

### Lifecycle Semantics

`factory.read()` uses `engine.connect()`:

- All repositories share one connection.
- Reads run in SQLAlchemy's implicit transaction.
- Closing the connection rolls back that implicit transaction.
- It does not promise a stable snapshot unless the isolation level provides one.

`factory.transaction()` uses `engine.begin()`:

- All repositories share one connection and outer transaction.
- Successful context exit commits.
- Exceptional context exit rolls back.
- Bound repositories must not commit or roll back independently.

## Repository Support

Repositories remain independently usable but optionally accept a bound connection. The existing `pass_or_acquire_connection` helper provides the required ownership behavior.

```python
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Self

from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass
class BaseRepository:
    db_engine: AsyncEngine
    connection: AsyncConnection | None = None

    @classmethod
    def instance(
        cls,
        db_engine: AsyncEngine,
        *,
        connection: AsyncConnection | None = None,
    ) -> Self:
        return cls(db_engine=db_engine, connection=connection)

    def connection_context(
        self,
    ) -> AbstractAsyncContextManager[AsyncConnection]:
        return pass_or_acquire_connection(
            self.db_engine,
            connection=self.connection,
        )
```

A repository read then works both independently and through a UoW:

```python
class CompRunsRepository(BaseRepository):
    async def get_latest_run_by_project(
        self,
        project_id: ProjectID,
    ) -> CompRunsAtDB:
        async with self.connection_context() as connection:
            result = await connection.execute(
                sa.select(comp_runs)
                .where(comp_runs.c.project_uuid == f"{project_id}")
                .order_by(comp_runs.c.run_id.desc())
                .limit(1)
            )
            row = result.one_or_none()

        if row is None:
            raise ComputationalRunNotFoundError
        return CompRunsAtDB.model_validate(row)
```

Without a UoW, `pass_or_acquire_connection` acquires and releases a connection. With a UoW, it yields the bound connection without closing it.

## Director-v2 Adapter

Director-v2 defines only its repository bundle and builder.

```python
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class DirectorV2Repositories:
    comp_pipelines: CompPipelinesRepository
    comp_runs: CompRunsRepository
    comp_tasks: CompTasksRepository
    projects: ProjectsRepository


def build_director_v2_repositories(
    engine: AsyncEngine,
    connection: AsyncConnection,
) -> DirectorV2Repositories:
    return DirectorV2Repositories(
        comp_pipelines=CompPipelinesRepository(engine, connection),
        comp_runs=CompRunsRepository(engine, connection),
        comp_tasks=CompTasksRepository(engine, connection),
        projects=ProjectsRepository(engine, connection),
    )


type DirectorV2UnitOfWorkFactory = AsyncpgUnitOfWorkFactory[
    DirectorV2Repositories
]
```

The FastAPI dependency returns a factory, not an entered UoW. It therefore does not reserve a connection for the whole request.

```python
def get_unit_of_work_factory(
    engine: Annotated[AsyncEngine, Depends(_get_db_engine)],
) -> DirectorV2UnitOfWorkFactory:
    return AsyncpgUnitOfWorkFactory(
        engine=engine,
        repository_builder=build_director_v2_repositories,
    )
```

## Director-v2 `get_computation`

The connection covers only sequential database reads. Graph processing and response construction happen after it has returned to the pool.

```python
async def get_computation(
    user_id: UserID,
    project_id: ProjectID,
    request: Request,
    uow_factory: Annotated[
        DirectorV2UnitOfWorkFactory,
        Depends(get_unit_of_work_factory),
    ],
) -> ComputationGet:
    async with uow_factory.read() as uow:
        if not await uow.repositories.projects.exists(project_id):
            raise ProjectNotFoundError(project_id=project_id)

        try:
            pipeline_dag, all_tasks, _filtered_tasks = await validate_pipeline(
                project_id,
                uow.repositories.comp_pipelines,
                uow.repositories.comp_tasks,
            )
        except PipelineTaskMissingError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The tasks referenced by the pipeline are missing",
            ) from exc

        last_run: CompRunsAtDB | None = None
        with contextlib.suppress(ComputationalRunNotFoundError):
            last_run = (
                await uow.repositories.comp_runs.get_latest_run_by_project(
                    project_id=project_id
                )
            )

    complete_dag = create_complete_dag_from_tasks(all_tasks)
    pipeline_details = await compute_pipeline_details(
        complete_dag,
        pipeline_dag,
        all_tasks,
    )
    pipeline_state = (
        last_run.result
        if last_run is not None
        else RunningState.NOT_STARTED
    )

    # Construct and return ComputationGet as before.
```

Queries on one asyncpg connection must remain sequential. Do not run them through `asyncio.gather` or an equivalent concurrency helper.

## Another Service Example

Storage uses the same generic `servicelib` implementation but defines a different bundle.

```python
@dataclass(frozen=True)
class StorageRepositories:
    file_metadata: FileMetaDataRepository


def build_storage_repositories(
    engine: AsyncEngine,
    connection: AsyncConnection,
) -> StorageRepositories:
    return StorageRepositories(
        file_metadata=FileMetaDataRepository(engine, connection),
    )


type StorageUnitOfWorkFactory = AsyncpgUnitOfWorkFactory[
    StorageRepositories
]
```

Usage exposes storage repositories instead of director-v2 repositories:

```python
async with storage_uow_factory.transaction() as uow:
    await uow.repositories.file_metadata.insert(file_metadata)
```

The generic types resolve independently:

```text
AsyncpgUnitOfWork[DirectorV2Repositories]
AsyncpgUnitOfWork[StorageRepositories]
```

There is no global repository collection and no direct dependency between services.

## Transactional Operations

A transactional UoW is appropriate when multiple database writes must commit atomically:

```python
async with uow_factory.transaction() as uow:
    await uow.repositories.comp_pipelines.upsert_pipeline(...)
    await uow.repositories.comp_tasks.upsert_tasks(...)
```

Before adopting this mode, write repositories must use the bound connection. They must not acquire an unrelated connection or independently commit.

Do not include external effects in this context:

```python
# Do not hold the transaction open around these operations.
await catalog_client.get(...)
await rabbitmq_client.request(...)
await stop_pipeline(...)
```

PostgreSQL cannot atomically roll back those effects. Workflows combining database writes and messages should use an outbox or another explicit consistency mechanism.

## Relationship to Existing Helpers

`pass_or_acquire_connection` remains the repository-level mechanism:

- A standalone repository call acquires and releases its own connection.
- A UoW-bound repository reuses the supplied connection.

`transaction_context` remains suitable for independently invoked write methods. For UoW-bound writes, transaction ownership must be explicit. Automatically creating a savepoint for every repository call adds overhead and can obscure atomicity; savepoints should be requested only where partial rollback is intended.

## Testing Strategy

Shared `servicelib` tests should verify:

- Context entry acquires exactly one connection.
- Context exit releases the connection after success and failure.
- Read mode does not commit.
- Transaction mode commits on success.
- Transaction mode rolls back on failure.
- Re-entering an active UoW fails clearly.
- Repository builder errors release the acquired connection.

Service tests should verify:

- Every repository in the bundle receives the same connection.
- Repository bundle typing exposes only that service's repositories.
- `get_computation` checks out one connection for its grouped reads.
- Existing route behavior and errors remain unchanged.
- The connection is released before graph processing or external calls.

A pool checkout assertion can use SQLAlchemy events:

```python
checkout_count = 0


def on_checkout(*_args: object) -> None:
    nonlocal checkout_count
    checkout_count += 1


event.listen(engine.sync_engine, "checkout", on_checkout)
try:
    await call_get_computation(...)
finally:
    event.remove(engine.sync_engine, "checkout", on_checkout)

assert checkout_count == 1
```

## Adoption Plan

1. Add and test the generic UoW and factory in `servicelib`.
2. Add optional bound-connection support to director-v2 `BaseRepository`.
3. Adapt `ProjectsRepository.exists`.
4. Adapt `CompPipelinesRepository.get_pipeline`.
5. Adapt `CompTasksRepository.list_tasks`.
6. Adapt `CompRunsRepository.get_latest_run_by_project`.
7. Add the director-v2 repository bundle and factory dependency.
8. Migrate only `get_computation` to a read UoW.
9. Measure route latency, pool checkout count, and pool utilization.
10. Consider `stop_computation`, releasing the UoW before `stop_pipeline`.
11. Introduce transactional UoWs only for operations with a clear atomic database boundary.

The `(project_uuid, run_id DESC)` index is complementary. Connection reuse reduces checkout and transaction overhead; the index reduces PostgreSQL execution work.
