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
    async def is_present(self, identifier: T, **extra_kwargs) -> bool:
        """Checks if a resource exists

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            True if the resource exists otherwise False
        """

    @abstractmethod
    async def create(self, **extra_kwargs) -> T:
        """Used for creating the resources

        Arguments:
            **extra_kwargs -- can be overloaded by the user

        Returns:
            user chosen identifier for the resource
        """

    @abstractmethod
    async def destroy(self, identifier: T, **extra_kwargs) -> None:
        """Used to destroy an existing resource

        Usually ``is_present`` will be called before attempting a removal.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user
        """

    async def safe_remove(self, identifier: T, **extra_kwargs) -> bool:
        """Removes the resource if is present.
        Logs errors, without re-raising.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            True if the resource was removed successfully otherwise false
        """
        is_present = await self.is_present(identifier, **extra_kwargs)
        if not is_present:
            return False

        with log_context(
            _logger, logging.DEBUG, f"{self.__class__}: removing {identifier}"
        ), log_catch(_logger, reraise=False):
            await self.destroy(identifier, **extra_kwargs)

        was_removed = await self.is_present(identifier, **extra_kwargs) is False
        if not was_removed:
            _logger.warning(
                "%s: resource %s could not be removed", self.__class__, identifier
            )
        return was_removed
