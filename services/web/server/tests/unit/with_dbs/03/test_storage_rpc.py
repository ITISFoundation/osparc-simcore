from pathlib import Path
from typing import Any, Callable

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_rpc_data_export.async_jobs import (
    AsyncJobRpcGet,
    AsyncJobRpcId,
)
from models_library.storage_schemas import DataExportPost
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole


@pytest.fixture
def create_storage_rpc_client_mock(mocker: MockerFixture) -> Callable[[str, Any], None]:
    def _(method: str, result_or_exception: Any):
        def side_effect(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception
            return result_or_exception

        mocker.patch(
            f"simcore_service_webserver.storage._handlers.{method}",
            side_effect=side_effect,
        )

    return _


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_data_export(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
):
    _task_id = AsyncJobRpcId(faker.uuid4())
    create_storage_rpc_client_mock(
        "start_data_export", AsyncJobRpcGet(task_id=_task_id, task_name=faker.text())
    )

    _body = DataExportPost(paths=[Path(".")])
    response = await client.post("/v0/storage/export-data", json=_body.model_dump())
    assert response.status == status.HTTP_202_ACCEPTED
