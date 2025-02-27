# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime
from typing import Protocol

from models_library.products import ProductName


class CreateFakeServiceDataCallable(Protocol):
    """Signature for services/catalog/tests/unit/with_dbs/conftest.py::create_fake_service_data"""

    def __call__(
        self,
        key,
        version,
        team_access: str | None = None,
        everyone_access: str | None = None,
        product: ProductName = "osparc",
        deprecated: datetime | None = None,  # DB column
    ):
        ...
