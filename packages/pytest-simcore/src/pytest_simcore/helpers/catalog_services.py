# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime
from typing import Any, Protocol

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
    ) -> tuple[dict[str, Any], ...]:
        """
        Returns a fake factory that creates catalog DATA that can be used to fill
        both services_meta_data and services_access_rights tables


        Example:
            fake_service, *fake_access_rights = create_fake_service_data(
                    "simcore/services/dynamic/jupyterlab",
                    "0.0.1",
                    team_access="xw",
                    everyone_access="x",
                    product=target_product,
                ),

            owner_access, team_access, everyone_access = fake_access_rights

        """
        ...
