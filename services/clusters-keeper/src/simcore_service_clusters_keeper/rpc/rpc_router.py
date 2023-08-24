from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])


@dataclass
class RPCRouter:
    routes: dict[str, Callable] = field(default_factory=dict)

    def expose(self) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.routes[func.__name__] = func
            return func

        return decorator
