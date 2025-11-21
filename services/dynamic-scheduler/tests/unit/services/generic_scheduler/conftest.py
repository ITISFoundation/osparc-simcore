from collections.abc import Callable, Iterable

import pytest
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    Operation,
    OperationName,
    OperationRegistry,
)


@pytest.fixture
def register_operation() -> Iterable[Callable[[OperationName, Operation], None]]:
    to_unregister: list[OperationName] = []

    def _(operation_name: OperationName, operation: Operation) -> None:
        OperationRegistry.register(operation_name, operation)
        to_unregister.append(operation_name)

    yield _

    for operation_name in to_unregister:
        OperationRegistry.unregister(operation_name)
