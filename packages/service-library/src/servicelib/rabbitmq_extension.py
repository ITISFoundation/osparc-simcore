import asyncio
import logging
from enum import Enum, auto
from typing import Any, Awaitable, Final, Iterable, Optional, Union

from pydantic import BaseModel, NonNegativeFloat, parse_raw_as
from servicelib.rabbitmq import RabbitMQClient
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


DEFAULT_FAST_RETRY_INTERVAL_S: Final[NonNegativeFloat] = 0.1
DEFAULT_RESOLVE_TIMEOUT_S: Final[NonNegativeFloat] = 2
RPC_RESOLVER_CHANNEL_NAME: Final[str] = "rpc.resolver.channel"


NamespacedMethodName = str
RPCLabel = str


class NamespacedMethodResolver:
    """
    Associates to a `namespaced_name` some labels.
    Provided labels will be cast to `str` and stored in a frozen set.
    """

    # TODO: have cache on top of this? or use a retry somewhere else?

    def __init__(self) -> None:
        self._namespace_method_to_labels: dict[
            NamespacedMethodName, frozenset[RPCLabel]
        ] = {}
        self._labels_to_namespace_method: dict[
            frozenset[RPCLabel], NamespacedMethodName
        ] = {}

    @staticmethod
    def get_frozen_labels(data: Iterable[Any]) -> frozenset[RPCLabel]:
        return frozenset(f"{x}" for x in data)

    def add(
        self, namespaced_method: NamespacedMethodName, labels: Iterable[Any]
    ) -> None:
        frozen_labels = self.get_frozen_labels(labels)
        self._namespace_method_to_labels[namespaced_method] = frozen_labels
        self._labels_to_namespace_method[frozen_labels] = namespaced_method

    def remove(
        self, namespaced_method: NamespacedMethodName, labels: Iterable[Any]
    ) -> None:
        # TODO: maybe check if the remove should only be done via
        # namespaced_method since this should be unique in the platform
        frozen_stored_labels = self._namespace_method_to_labels.get(
            namespaced_method, None
        )
        frozen_to_remove_labels = self.get_frozen_labels(labels)

        if frozen_stored_labels == frozen_to_remove_labels:
            self._namespace_method_to_labels.pop(namespaced_method, None)
            self._labels_to_namespace_method.pop(frozen_stored_labels, None)

    def get_namespaced_method(
        self, labels_to_match: Iterable[Any]
    ) -> Optional[NamespacedMethodName]:
        return self._labels_to_namespace_method.get(
            self.get_frozen_labels(labels_to_match), None
        )


##########################################


class RabbitNamespacedNameResolver:
    def __init__(
        self,
        rabbit_client: RabbitMQClient,
        namespaced_resolver: NamespacedMethodResolver,
    ) -> None:
        self.rabbit_client = rabbit_client
        self.namespaced_resolver = namespaced_resolver

    async def start(self) -> None:
        await self.rabbit_client.subscribe(
            RPC_RESOLVER_CHANNEL_NAME, self._resolver_handler
        )

    async def get_namespaced_method_for(
        self,
        labels: Iterable[Any],
        timeout: NonNegativeFloat = DEFAULT_RESOLVE_TIMEOUT_S,
        retry_interval: NonNegativeFloat = DEFAULT_FAST_RETRY_INTERVAL_S,
    ) -> NamespacedMethodName:
        """
        Resolves some `labels` to a `namespaced_method_name` corresponding
        to an RPC handler that can be called directly.
        For the given `labels` it first try to figure out if an entry for this was found
        locally.
        If the entry is not found it requests via pub/sub the information.
        If a reply is provided withing `timeout` seconds, this one will be returned
        If no entry is found raises `TimeoutError`.
        """

        logger.debug("Trying to resolve '%s' locally", labels)
        namespaced_method: NamespacedMethodName
        if namespaced_method := self.namespaced_resolver.get_namespaced_method(labels):
            logger.debug("Resolved '%s' locally to '%s'", labels, namespaced_method)
            return namespaced_method

        logger.debug("Trying to resolve '%s' via rabbit", labels)
        await self.rabbit_client.publish(
            RPC_RESOLVER_CHANNEL_NAME, RabbitMessageQueryForLabels(labels=labels).json()
        )

        try:
            async for attempt in AsyncRetrying(
                wait=wait_fixed(retry_interval),
                stop=stop_after_delay(timeout),
                reraise=True,
            ):
                with attempt:
                    namespaced_method: Optional[
                        NamespacedMethodName
                    ] = self.namespaced_resolver.get_namespaced_method(labels)
                    if namespaced_method is None:
                        raise TryAgain()

                    logger.debug(
                        "Resolved '%s' via rabbit to '%s'",
                        labels,
                        namespaced_method,
                    )
                    return namespaced_method
        except TryAgain as e:
            raise asyncio.TimeoutError(
                f"Could not resolve {labels=} after {timeout} seconds"
            ) from e

    async def remove_namespaced_method_with(
        self, namespaced_method: NamespacedMethodName, labels: Iterable[Any]
    ) -> None:
        """
        Propagates a message to remove previously received or locally stored
        `namespaced_method_name` together with it's associated `labels`.
        """
        await self.rabbit_client.publish(
            RPC_RESOLVER_CHANNEL_NAME,
            RabbitMessageRemoveNamespacedMethod(
                labels=labels, namespaced_method=namespaced_method
            ).json(),
        )

    async def _resolver_handler(self, data: bytes) -> None:
        parsed_rabbit_message = _parse_data(data)
        logger.debug("Handling message %s", parsed_rabbit_message)
        await _MAPPER_MESSAGE_HANDLERS[parsed_rabbit_message.message_type](
            self.rabbit_client, self.namespaced_resolver, parsed_rabbit_message
        )
        return True


class MessageType(str, Enum):
    # pydantic cannot distinguish between models with the same fields.
    # A field with a unique value is added to address this
    QUERY = auto()
    UPDATE = auto()
    REMOVE = auto()


class BaseRabbitMessage(BaseModel):
    message_type: MessageType


class RabbitMessageQueryForLabels(BaseRabbitMessage):
    message_type: MessageType = MessageType.QUERY
    labels: set[Any]


class RabbitMessageUpdateNamespacedMethod(RabbitMessageQueryForLabels):
    message_type: MessageType = MessageType.UPDATE
    namespaced_method: NamespacedMethodName


class RabbitMessageRemoveNamespacedMethod(RabbitMessageUpdateNamespacedMethod):
    message_type: MessageType = MessageType.REMOVE


def _parse_data(
    data: bytes,
) -> Union[
    RabbitMessageQueryForLabels,
    RabbitMessageUpdateNamespacedMethod,
    RabbitMessageRemoveNamespacedMethod,
]:
    """given a sequence of bytes returns the correct pydantic model"""
    message_type = BaseRabbitMessage.parse_raw(data).message_type
    return parse_raw_as(_MAPPER_MODEL_TYPE[message_type], data)


async def _handle_message_query_for_labels(
    rabbit_client: RabbitMQClient,
    namespaced_resolver: NamespacedMethodResolver,
    message: RabbitMessageQueryForLabels,
) -> None:
    namespaced_method = namespaced_resolver.get_namespaced_method(message.labels)
    if namespaced_method is None:
        logger.debug("No entry for '%s' found locally", message.labels)
        return

    await rabbit_client.publish(
        RPC_RESOLVER_CHANNEL_NAME,
        RabbitMessageUpdateNamespacedMethod(
            labels=message.labels,
            namespaced_method=namespaced_method,
        ).json(),
    )
    logger.debug(
        "Found '%s' locally mapped to '%s'. Notified all remotes",
        message.labels,
        namespaced_method,
    )


async def _handle_message_update_namespace_method(
    _: RabbitMQClient,
    namespaced_resolver: NamespacedMethodResolver,
    message: RabbitMessageUpdateNamespacedMethod,
) -> None:
    namespaced_resolver.add(
        namespaced_method=message.namespaced_method,
        labels=message.labels,
    )
    logger.debug(
        "Updating local with remote data '%s' to '%s'", message.labels, message
    )


async def _handle_message_remove_namespace_method(
    _: RabbitMQClient,
    namespaced_resolver: NamespacedMethodResolver,
    message: RabbitMessageRemoveNamespacedMethod,
):
    namespaced_resolver.remove(message.namespaced_method, message.labels)
    logger.debug(
        "Removing '%s' with labels '%s' from local store",
        message.namespaced_method,
        message.labels,
    )


_MAPPER_MODEL_TYPE: dict[MessageType, type] = {
    MessageType.QUERY: RabbitMessageQueryForLabels,
    MessageType.UPDATE: RabbitMessageUpdateNamespacedMethod,
    MessageType.REMOVE: RabbitMessageRemoveNamespacedMethod,
}

_MAPPER_MESSAGE_HANDLERS: dict[MessageType, Awaitable] = {
    MessageType.QUERY: _handle_message_query_for_labels,
    MessageType.UPDATE: _handle_message_update_namespace_method,
    MessageType.REMOVE: _handle_message_remove_namespace_method,
}

##########################################


class AdvancedRPC:
    def __init__(self, rabbit_client: RabbitMQClient) -> None:
        self.rabbit_client = rabbit_client
        self.namespaced_resolver = NamespacedMethodResolver()
        self.rabbit_resolver = RabbitNamespacedNameResolver(
            rabbit_client=rabbit_client, namespaced_resolver=self.namespaced_resolver
        )

    # TODO we cam register and unregister here all the RPC stuff
