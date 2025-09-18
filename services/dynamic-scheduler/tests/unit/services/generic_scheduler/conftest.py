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

    def _(opration_name: OperationName, operation: Operation) -> None:
        OperationRegistry.register(opration_name, operation)
        to_unregister.append(opration_name)

    yield _

    for opration_name in to_unregister:
        OperationRegistry.unregister(opration_name)
