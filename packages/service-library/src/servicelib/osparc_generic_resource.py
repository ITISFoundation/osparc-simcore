import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from servicelib.logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)

Ident = TypeVar("Ident")
Res = TypeVar("Res")


class BaseOsparcGenericResourceManager(ABC, Generic[Ident, Res]):
    """Common interface used to manage the lifecycle of osparc resources.

    An osparc resource can be anything that needs to be created and then removed
    during the runtime of the platform.

    Safe remove the resource.

    For usage check ``packages/service-library/tests/test_osparc_generic_resource.py``
    """

    # If True ``get_or_create`` will add the `identifier` calling ``create``.
    # Overwrite in constructor.
    GET_OR_CREATE_INJECTS_IDENTIFIER: bool = False

    @abstractmethod
    async def get(self, identifier: Ident, **extra_kwargs) -> Res | None:
        """Returns a resource if exits.

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

        Usually ``is_present`` will be called before attempting a removal.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user
        """

    async def safe_remove(self, identifier: Ident, **extra_kwargs) -> bool:
        """Removes the resource if is present.
        Logs errors, without re-raising.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            True if the resource was removed successfully otherwise false
        """
        if await self.get(identifier, **extra_kwargs) is None:
            return False

        with log_context(
            _logger, logging.DEBUG, f"{self.__class__}: removing {identifier}"
        ), log_catch(_logger, reraise=False):
            await self.destroy(identifier, **extra_kwargs)

        was_removed = await self.get(identifier, **extra_kwargs) is None
        if not was_removed:
            _logger.warning(
                "%s: resource %s could not be removed", self.__class__, identifier
            )
        return was_removed

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
