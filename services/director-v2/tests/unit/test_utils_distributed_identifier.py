# pylint:disable=protected-access
# pylint:disable=redefined-outer-name

import asyncio
import string
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from secrets import choice
from typing import Final
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, NonNegativeInt
from pytest_mock import MockerFixture
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_director_v2.utils.base_distributed_identifier import (
    BaseDistributedIdentifierManager,
)

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]

# if this goes too high, max open file limit is reached
_MAX_REDIS_CONCURRENCY: Final[NonNegativeInt] = 1000


class UserDefinedID:
    # define a custom type of ID for the API
    # by choice it is hard to serialize/deserialize

    def __init__(self, uuid: UUID | None = None) -> None:
        self._id = uuid if uuid else uuid4()

    def __eq__(self, other: "UserDefinedID") -> bool:
        return self._id == other._id

    # only necessary for nice looking IDs in the logs
    def __repr__(self) -> str:
        return f"<id={self._id}>"

    # only necessary for RandomTextAPI
    def __hash__(self):
        return hash(str(self._id))


class RandomTextEntry(BaseModel):
    text: str

    @classmethod
    def create(cls, length: int) -> "RandomTextEntry":
        letters_and_digits = string.ascii_letters + string.digits
        text = "".join(choice(letters_and_digits) for _ in range(length))
        return cls(text=text)


class RandomTextAPI:
    # Emulates an external API
    # used to create resources

    def __init__(self) -> None:
        self._created: dict[UserDefinedID, RandomTextEntry] = {}

    def create(self, length: int) -> tuple[UserDefinedID, RandomTextEntry]:
        identifier = UserDefinedID(uuid4())
        self._created[identifier] = RandomTextEntry.create(length)
        return identifier, self._created[identifier]

    def delete(self, identifier: UserDefinedID) -> None:
        del self._created[identifier]

    def get(self, identifier: UserDefinedID) -> RandomTextEntry | None:
        return self._created.get(identifier, None)


@dataclass
class ComponentUsingRandomText:
    # Emulates another component in the system
    # using the created resources

    _in_use: bool = True

    def is_used(self, an_id: UserDefinedID) -> bool:
        _ = an_id
        return self._in_use

    def toggle_usage(self, in_use: bool) -> None:
        self._in_use = in_use


class AnEmptyTextCleanupContext(BaseModel):
    # nothing is required during cleanup, so the context
    # is an empty object.
    # A ``pydantic.BaseModel`` is used for convenience
    # this could have inherited from ``object``
    ...


class RandomTextResourcesManager(
    BaseDistributedIdentifierManager[
        UserDefinedID, RandomTextEntry, AnEmptyTextCleanupContext
    ]
):
    # Implements a resource manager for handling the lifecycle of
    # resources created by a service.
    # It also comes in with automatic cleanup in case the service owing
    # the resources failed to removed them in the past.

    def __init__(
        self,
        redis_client_sdk: RedisClientSDK,
        component_using_random_text: ComponentUsingRandomText,
    ) -> None:
        # THESE two systems would normally come stored in the `app` context
        self.api = RandomTextAPI()
        self.component_using_random_text = component_using_random_text

        super().__init__(redis_client_sdk)

    @classmethod
    def _deserialize_identifier(cls, raw: str) -> UserDefinedID:
        return UserDefinedID(UUID(raw))

    @classmethod
    def _serialize_identifier(cls, identifier: UserDefinedID) -> str:
        return f"{identifier._id}"  # noqa: SLF001

    @classmethod
    def _deserialize_cleanup_context(
        cls, raw: str | bytes
    ) -> AnEmptyTextCleanupContext:
        return AnEmptyTextCleanupContext.model_validate_json(raw)

    @classmethod
    def _serialize_cleanup_context(
        cls, cleanup_context: AnEmptyTextCleanupContext
    ) -> str:
        return cleanup_context.model_dump_json()

    async def is_used(
        self, identifier: UserDefinedID, cleanup_context: AnEmptyTextCleanupContext
    ) -> bool:
        _ = cleanup_context
        return self.component_using_random_text.is_used(identifier)

    # NOTE: it is intended for the user to overwrite the **kwargs with custom names
    # to provide a cleaner interface, tooling will complain slightly
    async def _create(  # pylint:disable=arguments-differ # type:ignore [override]
        self, length: int
    ) -> tuple[UserDefinedID, RandomTextEntry]:
        return self.api.create(length)

    async def get(self, identifier: UserDefinedID, **_) -> RandomTextEntry | None:
        return self.api.get(identifier)

    async def _destroy(
        self, identifier: UserDefinedID, _: AnEmptyTextCleanupContext
    ) -> None:
        self.api.delete(identifier)


@pytest.fixture
async def redis_client_sdk(
    redis_service: RedisSettings,
) -> AsyncIterator[RedisClientSDK]:
    redis_resources_dns = redis_service.build_redis_dsn(
        RedisDatabase.DISTRIBUTED_IDENTIFIERS
    )

    client = RedisClientSDK(redis_resources_dns, client_name="pytest")
    assert client
    assert client.redis_dsn == redis_resources_dns
    await client.setup()
    # cleanup, previous run's leftovers
    await client.redis.flushall()

    yield client
    # cleanup, properly close the clients
    await client.redis.flushall()
    await client.shutdown()


@pytest.fixture
def component_using_random_text() -> ComponentUsingRandomText:
    return ComponentUsingRandomText()


@pytest.fixture
async def manager_with_no_cleanup_task(
    redis_client_sdk: RedisClientSDK,
    component_using_random_text: ComponentUsingRandomText,
) -> RandomTextResourcesManager:
    return RandomTextResourcesManager(redis_client_sdk, component_using_random_text)


@pytest.fixture
async def manager(
    manager_with_no_cleanup_task: RandomTextResourcesManager,
) -> AsyncIterable[RandomTextResourcesManager]:
    await manager_with_no_cleanup_task.setup()
    yield manager_with_no_cleanup_task
    await manager_with_no_cleanup_task.shutdown()


async def test_resource_is_missing(manager: RandomTextResourcesManager):
    missing_identifier = UserDefinedID()
    assert await manager.get(missing_identifier) is None


@pytest.mark.parametrize("delete_before_removal", [True, False])
async def test_full_workflow(
    manager: RandomTextResourcesManager, delete_before_removal: bool
):
    # creation
    identifier, _ = await manager.create(
        cleanup_context=AnEmptyTextCleanupContext(), length=1
    )
    assert await manager.get(identifier) is not None

    # optional removal
    if delete_before_removal:
        await manager.remove(identifier)

    is_still_present = not delete_before_removal
    assert (await manager.get(identifier) is not None) is is_still_present

    # safe remove the resource
    await manager.remove(identifier)

    # resource no longer exists
    assert await manager.get(identifier) is None


@pytest.mark.parametrize("reraise", [True, False])
async def test_remove_raises_error(
    mocker: MockerFixture,
    manager: RandomTextResourcesManager,
    caplog: pytest.LogCaptureFixture,
    reraise: bool,
):
    caplog.clear()

    error_message = "mock error during resource destroy"
    mocker.patch.object(manager, "_destroy", side_effect=RuntimeError(error_message))

    # after creation object is present
    identifier, _ = await manager.create(
        cleanup_context=AnEmptyTextCleanupContext(), length=1
    )
    assert await manager.get(identifier) is not None

    if reraise:
        with pytest.raises(RuntimeError):
            await manager.remove(identifier, reraise=reraise)
    else:
        await manager.remove(identifier, reraise=reraise)
    # check logs in case of error
    assert "Unhandled exception:" in caplog.text
    assert error_message in caplog.text


async def _create_resources(
    manager: RandomTextResourcesManager, count: int
) -> list[UserDefinedID]:
    creation_results: list[tuple[UserDefinedID, RandomTextEntry]] = await logged_gather(
        *[
            manager.create(cleanup_context=AnEmptyTextCleanupContext(), length=1)
            for _ in range(count)
        ],
        max_concurrency=_MAX_REDIS_CONCURRENCY,
    )
    return [x[0] for x in creation_results]


async def _assert_all_resources(
    manager: RandomTextResourcesManager,
    identifiers: list[UserDefinedID],
    *,
    exist: bool,
) -> None:
    get_results: list[RandomTextEntry | None] = await logged_gather(
        *[manager.get(identifier) for identifier in identifiers],
        max_concurrency=_MAX_REDIS_CONCURRENCY,
    )
    if exist:
        assert all(x is not None for x in get_results)
    else:
        assert all(x is None for x in get_results)


@pytest.mark.parametrize("count", [1000])
async def test_parallel_create_remove(manager: RandomTextResourcesManager, count: int):
    # create resources
    identifiers: list[UserDefinedID] = await _create_resources(manager, count)
    await _assert_all_resources(manager, identifiers, exist=True)

    # safe remove the resources, they do not exist any longer
    await asyncio.gather(*[manager.remove(identifier) for identifier in identifiers])
    await _assert_all_resources(manager, identifiers, exist=False)


async def test_background_removal_of_unused_resources(
    manager_with_no_cleanup_task: RandomTextResourcesManager,
    component_using_random_text: ComponentUsingRandomText,
):
    # create resources
    identifiers: list[UserDefinedID] = await _create_resources(
        manager_with_no_cleanup_task, 10_000
    )
    await _assert_all_resources(manager_with_no_cleanup_task, identifiers, exist=True)

    # call cleanup, all resources still exist
    await manager_with_no_cleanup_task._cleanup_unused_identifiers()  # noqa: SLF001
    await _assert_all_resources(manager_with_no_cleanup_task, identifiers, exist=True)

    # make resources unused in external system
    component_using_random_text.toggle_usage(in_use=False)
    await manager_with_no_cleanup_task._cleanup_unused_identifiers()  # noqa: SLF001
    await _assert_all_resources(manager_with_no_cleanup_task, identifiers, exist=False)


async def test_no_redis_key_overlap_when_inheriting(
    redis_client_sdk: RedisClientSDK,
    component_using_random_text: ComponentUsingRandomText,
):
    class ChildRandomTextResourcesManager(RandomTextResourcesManager):
        ...

    parent_manager = RandomTextResourcesManager(
        redis_client_sdk, component_using_random_text
    )
    child_manager = ChildRandomTextResourcesManager(
        redis_client_sdk, component_using_random_text
    )

    # create an entry in the child and one in the parent

    parent_identifier, _ = await parent_manager.create(
        cleanup_context=AnEmptyTextCleanupContext(), length=1
    )
    child_identifier, _ = await child_manager.create(
        cleanup_context=AnEmptyTextCleanupContext(), length=1
    )
    assert parent_identifier != child_identifier

    keys = await redis_client_sdk.redis.keys("*")
    assert len(keys) == 2

    # check keys contain the correct prefixes
    key_prefixes: set[str] = {k.split(":")[0] for k in keys}
    assert key_prefixes == {
        RandomTextResourcesManager.class_path(),
        ChildRandomTextResourcesManager.class_path(),
    }
