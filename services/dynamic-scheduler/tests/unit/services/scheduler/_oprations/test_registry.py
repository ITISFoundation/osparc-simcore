# pylint:disable=protected-access

from pydantic import NonNegativeInt
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    OperationRegistry,
)
from simcore_service_dynamic_scheduler.services.scheduler._operations.registry import (
    register_operataions,
    unregister_operations,
)


def _ensure_registered_operations(*, count: NonNegativeInt) -> None:
    assert len(OperationRegistry._OPERATIONS) == count  # noqa: SLF001


def test_register_unregister_operations() -> None:
    _ensure_registered_operations(count=0)
    register_operataions()
    _ensure_registered_operations(count=7)
    unregister_operations()
    _ensure_registered_operations(count=0)
