import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from servicelib.logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseOsparcGenericResourceManager(ABC, Generic[T]):
    """Common interface used to manage the lifecycle of osparc resources.

    An osparc resource can be anything that needs to be created and then removed
    during the runtime of the platform.

    Safe remove the resource.

    For usage check ``packages/service-library/tests/test_osparc_generic_resource.py``
    """

    @abstractmethod
    async def is_present(self, identifier: T) -> bool:
        """Checks if a resource exists

        Arguments:
            identifier -- user chosen identifier for the resource

        Returns:
            True if the resource exists otherwise False
        """

    @abstractmethod
    async def create(self, **kwargs) -> T:
        """Used for creating the resources

        Arguments:
            **kwargs -- overloaded with required arguments to create the resource

        Returns:
            user chosen identifier for the resource
        """

    @abstractmethod
    async def destroy(self, identifier: T) -> None:
        """Used to destroy an existing resource

        Usually ``is_present`` will be called before attempting a removal.

        Arguments:
            identifier -- user chosen identifier for the resource
        """

    async def safe_remove(self, identifier: T) -> bool:
        """Removes the resource if is present.
        Logs errors, without re-raising.

        Arguments:
            identifier -- user chosen identifier for the resource

        Returns:
            True if the resource was removed successfully otherwise false
        """
        if await self.is_present(identifier):
            with log_context(
                _logger, logging.WARNING, f"Removing {identifier}"
            ), log_catch(_logger, reraise=False):
                await self.destroy(identifier)
                return True
        return False
