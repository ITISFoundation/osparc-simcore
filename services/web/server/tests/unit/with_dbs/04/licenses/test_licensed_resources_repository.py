# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
import arrow
import pytest
from aiohttp.test_utils import TestClient
from models_library.licenses import (
    VIP_DETAILS_EXAMPLE,
    LicensedResourcePatchDB,
    LicensedResourceType,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.licenses import _licensed_resources_repository
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_licensed_items_db_trash(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    pricing_plan_id: int,
):
    assert client.app

    # Create two licensed items
    licensed_resource_ids = []
    for name in ["Model A", "Model B"]:
        licensed_resource_db = (
            await _licensed_resources_repository.create_if_not_exists(
                client.app,
                display_name="Model A Display Name",
                licensed_resource_name=name,
                licensed_resource_type=LicensedResourceType.VIP_MODEL,
                licensed_resource_data=VIP_DETAILS_EXAMPLE,
            )
        )
        licensed_resource_ids.append(licensed_resource_db.licensed_resource_id)

    # Trash one licensed item
    trashing_at = arrow.now().datetime
    trashed_item = await _licensed_resources_repository.update(
        client.app,
        licensed_resource_id=licensed_resource_ids[0],
        updates=LicensedResourcePatchDB(trash=True),
    )

    assert trashed_item.licensed_resource_id == licensed_resource_ids[0]
    assert trashed_item.trashed
    assert trashing_at < trashed_item.trashed
    assert trashed_item.trashed < arrow.now().datetime
