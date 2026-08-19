import pytest
from models_library.projects import ProjectID
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient, RPCNotInitializedError
from servicelib.rabbitmq.rpc_interfaces.director_v2 import computations
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ComputationRunStatesRetrievalError,
)


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
