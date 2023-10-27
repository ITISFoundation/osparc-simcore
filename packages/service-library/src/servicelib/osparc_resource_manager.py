from abc import abstractmethod
from dataclasses import dataclass, field
from enum import auto
from typing import Any, Final, TypeAlias

from models_library.utils.enums import StrAutoEnum
from servicelib.redis import RedisClientSDK

ResourceIdentifier: TypeAlias = str

_RESOURCE_PREFIX: Final[str] = "RESOURCE"
_LOCK_PREFIX: Final[str] = "LOCK"

# NOTE: whens keeping track of resources the value is not required
# everything is encoded in the key
_RESOURCE_KEY_VALUE: Final[str] = ""


class BaseResourceHandler:
    """Used as basis for"""

    @abstractmethod
    async def is_present(self, identifier: ResourceIdentifier) -> bool:
        """Checks whether the resource is still present in the system

        The resource can be a docker network, a user service a volume etc...
        """

    @abstractmethod
    async def destroy(self, identifier: ResourceIdentifier) -> None:
        ...

    @abstractmethod
    async def create(self, identifier: ResourceIdentifier, **kwargs: Any) -> None:
        ...


class OsparcResourceType(StrAutoEnum):
    """Types of resources that are tracked by oSPARC"""

    SERVICE = auto()


def _key_space(resource_type: OsparcResourceType, prefix: str) -> str:
    return f"{prefix}:{resource_type}"


def _get_key_lock_name(
    resource_type: OsparcResourceType, identifier: ResourceIdentifier
) -> str:
    return f"{_key_space(resource_type,_LOCK_PREFIX)}:{identifier}"


def _get_key_resource_name(
    resource_type: OsparcResourceType, identifier: ResourceIdentifier
) -> str:
    return f"{_key_space(resource_type,_RESOURCE_PREFIX)}:{identifier}"


@dataclass
class OsparcResoruceManager:
    """Allows to track and manage the lifecycle of resource inside oSPARc"""

    redis_client_sdk: RedisClientSDK
    registered_handlers: dict[OsparcResourceType, BaseResourceHandler] = field(
        default_factory=dict
    )

    def _get_handler(self, resource_type: OsparcResourceType) -> BaseResourceHandler:
        return self.registered_handlers[resource_type]

    def register(
        self,
        resource_type: OsparcResourceType,
        *,
        resource_handler: BaseResourceHandler,
    ) -> None:
        """Register an optional resource handler to manage the lifecycle of the resource

        Arguments:
            resource_type -- the type of resource which should be handled
            resource_handler -- implements the lifecycle methods for the resource type
        """
        self.registered_handlers[resource_type] = resource_handler

    async def add(
        self,
        resource_type: OsparcResourceType,
        *,
        identifier: ResourceIdentifier,
        create: bool = False,
        **kwargs: Any,
    ) -> None:
        """Keep track of a resource, optionally creates the resource if missing

        Arguments:
            resource_type -- the type of resource which should be tracked
            identifier -- unique identifier for inside oSPARC

        Keyword Arguments:
            create -- when True creates the resource if missing (default: {False})
            kwargs -- are passed as arguments to `BaseResourceHandler.create` and can be
                used to initialize the resource
        """

        async with self.redis_client_sdk.lock_context(
            _get_key_lock_name(resource_type, identifier),
            blocking=True,
            blocking_timeout_s=None,
        ):
            if create and not await self._get_handler(resource_type).is_present(
                identifier
            ):
                await self._get_handler(resource_type).create(identifier, **kwargs)

            key = _get_key_resource_name(resource_type, identifier)
            await self.redis_client_sdk.redis.set(key, _RESOURCE_KEY_VALUE)

    async def remove(
        self,
        resource_type: OsparcResourceType,
        *,
        identifier: ResourceIdentifier,
        destroy: bool = False,
    ) -> None:
        """Remove resource from tracking, optionally destroys the resources if present

        Arguments:
            resource_type -- the type of resource which is tracked
            identifier -- unique identifier for inside oSPARC

        Keyword Arguments:
            destroy -- when True destroys the resource if present (default: {False})
        """

        async with self.redis_client_sdk.lock_context(
            _get_key_lock_name(resource_type, identifier),
            blocking=True,
            blocking_timeout_s=None,
        ):
            if destroy and await self._get_handler(resource_type).is_present(
                identifier
            ):
                await self._get_handler(resource_type).destroy(identifier)

            key = _get_key_resource_name(resource_type, identifier)
            await self.redis_client_sdk.redis.delete(key)

    async def get_resources(
        self, resource_type: OsparcResourceType
    ) -> set[ResourceIdentifier]:
        """returns all identifiers for a given resource type

        Arguments:
            resource_type -- the type of resource which is tracked

        Returns:
            all currently tracked resources of the provided resource type
        """
        keys_prefix = f"{_key_space(resource_type, _RESOURCE_PREFIX)}:"
        found_keys = await self.redis_client_sdk.redis.keys(f"{keys_prefix}*")
        return {key.removeprefix(keys_prefix) for key in found_keys}
