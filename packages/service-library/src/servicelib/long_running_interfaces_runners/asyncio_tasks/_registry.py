from collections.abc import Callable
from typing import Any, Self, TypeVar

from ...long_running_interfaces import RemoteHandlerName

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])


class AsyncTaskRegistry:
    def __init__(self) -> None:
        self.handlers: dict[RemoteHandlerName, Callable] = {}

    def _raise_if_registered(self, name: RemoteHandlerName) -> None:
        if name in self.handlers:
            msg = f"Job '{name}' is already registered."
            raise ValueError(msg)

    def expose(
        self,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """
        Decorator to register an async function with an optional name.
        """

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            name: str = func.__name__
            self._raise_if_registered(name)
            self.handlers[name] = func

            return func

        return decorator

    def include(self, other: Self) -> None:
        for name, handler in other.handlers.items():
            self._raise_if_registered(name)
            self.handlers[name] = handler
