from uuid import uuid4

import pytest
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationRunStateBatchGetProjectIDs,
)
from models_library.projects import ProjectID
from pydantic import TypeAdapter, ValidationError
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient, RPCNotInitializedError
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ComputationRunStatesRetrievalError,
)

pytestmark = pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors


async def test_batch_get_computations_latest_states_enforces_maximum_batch_size(
    mocker: MockerFixture,
):
    rpc_client = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_client.request = mocker.AsyncMock(return_value=[])
    max_batch_size = TypeAdapter(ComputationRunStateBatchGetProjectIDs).json_schema()["maxItems"]

    assert (
        await computations.batch_get_computations_latest_states(
            rpc_client,
            project_ids=[ProjectID(f"{uuid4()}") for _ in range(max_batch_size)],
        )
        == []
    )
    rpc_client.request.assert_awaited_once()

    rpc_client.request.reset_mock()
    with pytest.raises(ValidationError, match=f"at most {max_batch_size} items"):
        await computations.batch_get_computations_latest_states(
            rpc_client,
            project_ids=[ProjectID(f"{uuid4()}") for _ in range(max_batch_size + 1)],
        )
    rpc_client.request.assert_not_awaited()


@pytest.mark.parametrize("rpc_error", [RPCNotInitializedError(), TimeoutError()])
async def test_list_computations_latest_states_translates_rpc_errors(
    mocker: MockerFixture,
    rpc_error: BaseException,
):
    rpc_client = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_client.request = mocker.AsyncMock(side_effect=rpc_error)

    with pytest.raises(ComputationRunStatesRetrievalError):
        await computations.batch_get_computations_latest_states(
            rpc_client,
            project_ids=[ProjectID("de2578c5-431e-6257-a462-d7bf73b76c0c")],
        )
