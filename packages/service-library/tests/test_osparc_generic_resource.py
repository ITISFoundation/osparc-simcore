# pylint:disable=redefined-outer-name

import random
import string
from typing import Any
from uuid import UUID, uuid4

import pytest
from pytest_mock import MockerFixture
from servicelib.osparc_generic_resource import BaseOsparcGenericResourcesManager


# define a custom type of ID for the API
class UserDefinedID:
    def __init__(self, uuid: UUID | None = None) -> None:
        self._id = uuid if uuid else uuid4()

    def __eq__(self, other: "UserDefinedID") -> bool:
        return self._id == other._id

    def __hash__(self):
        return hash(str(self._id))


# mocked api interface
class RandomTextAPI:
    def __init__(self) -> None:
        self._created: dict[UserDefinedID, Any] = {}

    @staticmethod
    def _random_string(length: int) -> str:
        letters_and_digits = string.ascii_letters + string.digits
        return "".join(
            random.choice(letters_and_digits) for _ in range(length)  # noqa: S311
        )

    def create(self, length: int) -> tuple[UserDefinedID, Any]:
        identifier = UserDefinedID(uuid4())
        self._created[identifier] = self._random_string(length)
        return identifier, self._created[identifier]

    def delete(self, identifier: UserDefinedID) -> None:
        del self._created[identifier]

    def get(self, identifier: UserDefinedID) -> Any | None:
        return self._created.get(identifier, None)


# define a custom manager using the custom user defined identifiers
# NOTE: note that the generic uses `[UserDefinedID, Any]`
# which enforces typing constraints on the overloaded abstract methods
class RandomTextResourcesManager(BaseOsparcGenericResourcesManager[UserDefinedID, Any]):
    # pylint:disable=arguments-differ

    def __init__(self) -> None:
        self.api = RandomTextAPI()

    async def get(self, identifier: UserDefinedID, **_) -> Any | None:
        return self.api.get(identifier)

    async def create(self, length: int) -> tuple[UserDefinedID, Any]:
        return self.api.create(length)

    async def destroy(self, identifier: UserDefinedID) -> None:
        self.api.delete(identifier)


@pytest.fixture
def manager() -> RandomTextResourcesManager:
    return RandomTextResourcesManager()


async def test_resource_is_missing(manager: RandomTextResourcesManager):
    missing_identifier = UserDefinedID()
    assert await manager.get(missing_identifier) is None


async def test_manual_workflow(manager: RandomTextResourcesManager):
    # creation
    identifier, _ = await manager.create(length=1)
    assert await manager.get(identifier) is not None

    # removal
    await manager.destroy(identifier)

    # resource no longer exists
    assert await manager.get(identifier) is None


@pytest.mark.parametrize("delete_before_removal", [True, False])
async def test_automatic_cleanup_workflow(
    manager: RandomTextResourcesManager, delete_before_removal: bool
):
    # creation
    identifier, _ = await manager.create(length=1)
    assert await manager.get(identifier) is not None

    # optional removal
    if delete_before_removal:
        await manager.destroy(identifier)

    is_still_present = not delete_before_removal
    assert (await manager.get(identifier) is not None) is is_still_present

    # safe remove the resource
    expected_safe_removal_result = not delete_before_removal
    assert await manager.safe_remove(identifier) is expected_safe_removal_result

    # resource no longer exists
    assert await manager.get(identifier) is None


async def test_safe_remove_api_raises_error(
    mocker: MockerFixture,
    manager: RandomTextResourcesManager,
    caplog: pytest.LogCaptureFixture,
):
    caplog.clear()

    error_message = "mock error during resource destroy"
    mocker.patch.object(manager, "destroy", side_effect=RuntimeError(error_message))

    # after creation object is present
    identifier, _ = await manager.create(length=1)
    assert await manager.get(identifier) is not None

    # report failed to remove and log
    assert await manager.safe_remove(identifier) is False
    assert error_message in caplog.text
    assert "could not be removed" in caplog.text


async def test_get_or_create_exiting(manager: RandomTextResourcesManager):
    exiting_identifier, exiting_obj = manager.api.create(length=1)
    # query an existing identifier
    identifier, obj = await manager.get_or_create(
        identifier=exiting_identifier, length=1
    )
    assert identifier == exiting_identifier
    assert obj == exiting_obj


async def test_get_or_create_creates_identifier(manager: RandomTextResourcesManager):
    # creates an identifier
    new_identifier, new_obj = await manager.get_or_create(length=1)
    new_identifier_1, obj1 = await manager.get_or_create(
        identifier=new_identifier,
        # NOTE extra_kwargs are ignored when the object already exists
        length=2,
    )
    assert new_identifier == new_identifier_1
    assert new_obj == obj1


async def test_get_or_create_creates_identifier_when_provided_identifier_is_missing(
    manager: RandomTextResourcesManager,
):
    missing_identifier = UserDefinedID(uuid4())
    assert await manager.get(missing_identifier) is None

    new_identifier, _ = await manager.get_or_create(
        identifier=missing_identifier, length=1
    )
    assert new_identifier != missing_identifier


async def test_get_or_create_with_identifier():
    class ManagerInjectingIdentifier(RandomTextResourcesManager):
        def __init__(self) -> None:
            super().__init__()
            self.GET_OR_CREATE_INJECTS_IDENTIFIER = True

    manager = ManagerInjectingIdentifier()
    with pytest.raises(TypeError, match="identifier"):
        await manager.get_or_create(length=1)

    class FixedManagerInjectingIdentifier(ManagerInjectingIdentifier):
        # pylint:disable=arguments-differ
        async def create(
            self, length: int, identifier: UserDefinedID
        ) -> tuple[UserDefinedID, Any]:
            _ = identifier
            return await super().create(length)

    fixed_manager = FixedManagerInjectingIdentifier()
    await fixed_manager.get_or_create(length=1)
