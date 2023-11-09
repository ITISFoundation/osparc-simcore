# pylint:disable=redefined-outer-name

from typing import Any
from uuid import UUID, uuid4

import pytest
from pytest_mock import MockerFixture
from servicelib.osparc_generic_resource import BaseOsparcGenericResourceManager


# define a custom type of ID for the API
class UserDefinedID:
    def __init__(self, uuid: UUID | None = None) -> None:
        self._id = uuid if uuid else uuid4()


# a mock API interface
class RandomTextAPI:
    def __init__(self) -> None:
        self._created: dict[UserDefinedID, Any] = {}

    def create(self, length: int) -> UserDefinedID:
        """creates and returns identifier"""
        identifier = UserDefinedID(uuid4())
        self._created[identifier] = "a" * length
        return identifier

    def delete(self, identifier: UserDefinedID) -> None:
        del self._created[identifier]

    def already_exists(self, identifier: UserDefinedID) -> bool:
        return identifier in self._created


# define a custom manager using the custom user defined identifiers
# NOTE: note that the generic uses `UserDefinedID` which enforces typing constraints
# on the overloaded abstract methods
class RandomTextResoruceManager(BaseOsparcGenericResourceManager[UserDefinedID]):
    # pylint:disable=arguments-differ

    def __init__(self) -> None:
        self._api = RandomTextAPI()

    async def is_present(self, identifier: UserDefinedID) -> bool:
        return self._api.already_exists(identifier)

    async def create(self, length: int) -> UserDefinedID:
        return self._api.create(length)

    async def destroy(self, identifier: UserDefinedID) -> None:
        self._api.delete(identifier)


@pytest.fixture
def manager() -> RandomTextResoruceManager:
    return RandomTextResoruceManager()


async def test_resource_is_missing(manager: RandomTextResoruceManager):
    missing_identifier = UserDefinedID()
    assert await manager.is_present(missing_identifier) is False


async def test_manual_workflow(manager: RandomTextResoruceManager):
    # creation
    identifier: UserDefinedID = await manager.create(length=1)
    assert await manager.is_present(identifier) is True

    # removal
    await manager.destroy(identifier)

    # resource no longer exists
    assert await manager.is_present(identifier) is False


@pytest.mark.parametrize("delete_before_removal", [True, False])
async def test_automatic_cleanup_workflow(
    manager: RandomTextResoruceManager, delete_before_removal: bool
):
    # creation
    identifier: UserDefinedID = await manager.create(length=1)
    assert await manager.is_present(identifier) is True

    # optional removal
    if delete_before_removal:
        await manager.destroy(identifier)

    is_still_present = not delete_before_removal
    assert await manager.is_present(identifier) is is_still_present

    # safe remove the resource
    expected_safe_removal_result = not delete_before_removal
    assert await manager.safe_remove(identifier) is expected_safe_removal_result

    # resource no longer exists
    assert await manager.is_present(identifier) is False


async def test_safe_remove_api_raises_error(
    mocker: MockerFixture,
    manager: RandomTextResoruceManager,
    caplog: pytest.LogCaptureFixture,
):
    caplog.clear()

    error_message = "mock error during resource destroy"
    mocker.patch.object(manager, "destroy", side_effect=RuntimeError(error_message))

    # after creation object is present
    identifier: UserDefinedID = await manager.create(length=1)
    assert await manager.is_present(identifier) is True

    # report failed to remove and log
    assert await manager.safe_remove(identifier) is False
    assert error_message in caplog.text
