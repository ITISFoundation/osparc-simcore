from collections.abc import Callable
from typing import Any, Protocol

from pytest_mock import MockType


class HandlerMockFactory(Protocol):
    def __call__(
        self,
        handler_name: str,
        return_value: Any = None,
        exception: Exception | None = None,
        side_effect: Callable | None = None,
    ) -> MockType: ...
