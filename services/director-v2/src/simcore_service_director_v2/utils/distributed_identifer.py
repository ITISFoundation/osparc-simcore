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

    # If True ``get_or_create`` will add the `identifier` calling ``create``.
    GET_OR_CREATE_INJECTS_IDENTIFIER: bool = False

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

        NOTE: setting `GET_OR_CREATE_INJECTS_IDENTIFIER` will provide
        the ``identifier``as an argument when this is called by
        ``get_or_create``.

        Arguments:
            **extra_kwargs -- can be overloaded by the user

        Returns:
            tuple[identifier for the resource, resource object]
        """

    @abstractmethod
    async def destroy(self, identifier: Ident, **extra_kwargs) -> None:
        """Used to destroy an existing resource

        Usually ``get`` will be called before attempting a removal.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user
        """

    async def safe_remove(
        self, identifier: Ident, *, reraise: bool = False, **extra_kwargs
    ) -> None:
        """Removes the resource if is present,
        by default it does not reraise any error.

        Arguments:
            identifier -- user chosen identifier for the resource
            reraise -- when True raises any exception raised by ``destroy`` (default: {False})
            **extra_kwargs -- can be overloaded by the user

        Returns:
            True if the resource was removed successfully otherwise False
        """
        with log_context(
            _logger, logging.DEBUG, f"{self.__class__}: removing {identifier}"
        ), log_catch(_logger, reraise=reraise):
            await self.destroy(identifier, **extra_kwargs)

    # TODO: we do not require this pattern here, it can be added to the handlers that create it
    async def get_or_create(
        self, identifier: Ident | None = None, **extra_kwargs
    ) -> tuple[Ident, Res]:
        """Creates or returns an existing resource if an ``identifier`` is provided.

        NOTE: when a resource is created, it could return a new identifier.
        **ALWAYS** overwrite your previous identifier with
        the one returned by this function!

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            tuple[identifier for the resource, resource object]
        """
        if identifier:
            resource: Res | None = await self.get(identifier, **extra_kwargs)
            if resource:
                return identifier, resource

        if self.GET_OR_CREATE_INJECTS_IDENTIFIER:
            extra_kwargs["identifier"] = identifier

        return await self.create(**extra_kwargs)
