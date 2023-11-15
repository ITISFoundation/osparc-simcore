import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from servicelib.logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)

Ident = TypeVar("Ident")
Res = TypeVar("Res")


class BaseDistributedIdentifierManager(ABC, Generic[Ident, Res]):
    """Common interface used to manage the lifecycle of osparc resources.

    An osparc resource can be anything that needs to be created and then removed
    during the runtime of the platform.

    Safe remove the resource.

    For usage check ``packages/service-library/tests/test_osparc_generic_resource.py``
    """

    @abstractmethod
    async def get(self, identifier: Ident, **extra_kwargs) -> Res | None:
        """Returns a resource if exists.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            None if the resource does not exit
        """

    @abstractmethod
    async def create(self, **extra_kwargs) -> tuple[Ident, Res]:
        """Used for creating the resources

        Arguments:
            **extra_kwargs -- can be overloaded by the user

        Returns:
            tuple[identifier for the resource, resource object]
        """

    @abstractmethod
    async def destroy(self, identifier: Ident, **extra_kwargs) -> None:
        """Used to destroy an existing resource

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user
        """

    async def remove(
        self, identifier: Ident, *, reraise: bool = False, **extra_kwargs
    ) -> None:
        """Attempts to remove the resource, if an error occurs it is logged.

        Arguments:
            identifier -- user chosen identifier for the resource
            reraise -- when True raises any exception raised by ``destroy`` (default: {False})
            **extra_kwargs -- can be overloaded by the user
        """
        with log_context(
            _logger, logging.DEBUG, f"{self.__class__}: removing {identifier}"
        ), log_catch(_logger, reraise=reraise):
            await self.destroy(identifier, **extra_kwargs)
