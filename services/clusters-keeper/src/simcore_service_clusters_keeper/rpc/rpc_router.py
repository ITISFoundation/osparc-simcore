import functools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import SecretStr
from servicelib.logging_utils import log_catch, log_context

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])

_logger = logging.getLogger(__name__)

_RPC_CUSTOM_ENCODER: dict[Any, Callable[[Any], Any]] = {
    SecretStr: SecretStr.get_secret_value
}


@dataclass
class RPCRouter:
    routes: dict[str, Callable] = field(default_factory=dict)

    def expose(self) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with log_context(
                    _logger,
                    logging.INFO,
                    msg=f"calling {func.__name__} with {args}, {kwargs}",
                ), log_catch(_logger, reraise=True):
                    return json.dumps(
                        jsonable_encoder(
                            await func(*args, **kwargs),
                            custom_encoder=_RPC_CUSTOM_ENCODER,
                        )
                    )

            self.routes[func.__name__] = wrapper
            return func

        return decorator
