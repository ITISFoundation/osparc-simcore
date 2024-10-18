# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
from collections.abc import Awaitable, Callable, Iterator

import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient, RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler import services
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
    "rabbit",
]


@pytest.fixture
def node_id_new_style(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_legacy(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_not_found(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def service_status_new_style() -> DynamicServiceGet:
    return TypeAdapter(DynamicServiceGet).validate_python(
        DynamicServiceGet.model_config["json_schema_extra"]["examples"][1]
    )


@pytest.fixture
def service_status_legacy() -> NodeGet:
    return TypeAdapter(NodeGet).validate_python(
        NodeGet.model_config["json_schema_extra"]["examples"][1]
    )


@pytest.fixture
def fake_director_v0_base_url() -> str:
    return "http://fake-director-v0"


@pytest.fixture
def mock_director_v0_service_state(
    fake_director_v0_base_url: str,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_legacy: NodeGet,
) -> Iterator[None]:
    with respx.mock(
        base_url=fake_director_v0_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/fake-status/{node_id_legacy}").respond(
            status.HTTP_200_OK,
            text=json.dumps(
                jsonable_encoder({"data": service_status_legacy.model_dump()})
            ),
        )

        # service was not found response
        mock.get(f"fake-status/{node_not_found}").respond(status.HTTP_404_NOT_FOUND)

        yield None


@pytest.fixture
def mock_director_v2_service_state(
    node_id_new_style: NodeID,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_new_style: DynamicServiceGet,
    fake_director_v0_base_url: str,
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get(f"/dynamic_services/{node_id_new_style}").respond(
            status.HTTP_200_OK, text=service_status_new_style.model_dump_json()
        )

        # emulate redirect response to director-v0

        # this will provide a reply
        mock.get(f"/dynamic_services/{node_id_legacy}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "Location": f"{fake_director_v0_base_url}/fake-status/{node_id_legacy}"
            },
        )

        # will result in not being found
        mock.get(f"/dynamic_services/{node_not_found}").respond(
            status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                "Location": f"{fake_director_v0_base_url}/fake-status/{node_not_found}"
            },
        )

        yield None


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def rpc_client(
    app_environment: EnvVarsDict,
    mock_director_v2_service_state: None,
    mock_director_v0_service_state: None,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_get_state(
    rpc_client: RabbitMQRPCClient,
    node_id_new_style: NodeID,
    node_id_legacy: NodeID,
    node_not_found: NodeID,
    service_status_new_style: DynamicServiceGet,
    service_status_legacy: NodeGet,
):
    # status from director-v2

    result = await services.get_service_status(rpc_client, node_id=node_id_new_style)
    assert result == service_status_new_style

    # status from director-v0
    result = await services.get_service_status(rpc_client, node_id=node_id_legacy)
    assert result == service_status_legacy

    # node not tracked any of the two directors
    result = await services.get_service_status(rpc_client, node_id=node_not_found)
    assert result == NodeGetIdle.from_node_id(node_not_found)


@pytest.fixture
def dynamic_service_start() -> DynamicServiceStart:
    # one for legacy and one for new style?
    return TypeAdapter(DynamicServiceStart).validate_python(
        DynamicServiceStart.model_config["json_schema_extra"]["example"]
    )


@pytest.fixture
def mock_director_v0_service_run(
    fake_director_v0_base_url: str, service_status_legacy: NodeGet
) -> Iterator[None]:
    with respx.mock(
        base_url=fake_director_v0_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.post("/fake-service-run").respond(
            status.HTTP_201_CREATED,
            text=json.dumps(
                jsonable_encoder({"data": service_status_legacy.model_dump()})
            ),
        )

        yield None


@pytest.fixture
def mock_director_v2_service_run(
    is_legacy: bool,
    service_status_new_style: DynamicServiceGet,
    service_status_legacy: NodeGet,
    fake_director_v0_base_url: str,
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        request = mock.post("/dynamic_services")
        if is_legacy:
            request.respond(
                status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"{fake_director_v0_base_url}/fake-service-run"},
            )
        else:
            request.respond(
                status.HTTP_201_CREATED,
                text=service_status_new_style.model_dump_json(),
            )
        yield None


@pytest.mark.parametrize("is_legacy", [True, False])
async def test_run_dynamic_service(
    mock_director_v0_service_run: None,
    mock_director_v2_service_run: None,
    rpc_client: RabbitMQRPCClient,
    dynamic_service_start: DynamicServiceStart,
    is_legacy: bool,
):
    result = await services.run_dynamic_service(
        rpc_client, dynamic_service_start=dynamic_service_start
    )

    if is_legacy:
        assert isinstance(result, NodeGet)
    else:
        assert isinstance(result, DynamicServiceGet)


@pytest.fixture
def simcore_user_agent(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_not_found(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_manual_intervention(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def user_id() -> UserID:
    return 42


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_director_v0_service_stop(
    fake_director_v0_base_url: str,
    node_id: NodeID,
    node_id_not_found: NodeID,
    node_id_manual_intervention: NodeID,
    save_state: bool,
) -> Iterator[None]:
    can_save_str = f"{save_state}".lower()
    with respx.mock(
        base_url=fake_director_v0_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.delete(f"/fake-service-stop-ok/{node_id}?can_save={can_save_str}").respond(
            status.HTTP_204_NO_CONTENT
        )

        mock.delete(
            f"/fake-service-stop-not-found/{node_id_not_found}?can_save={can_save_str}"
        ).respond(status.HTTP_404_NOT_FOUND)

        mock.delete(
            f"/fake-service-stop-manual/{node_id_manual_intervention}?can_save={can_save_str}"
        ).respond(status.HTTP_409_CONFLICT)

        yield None


@pytest.fixture
def mock_director_v2_service_stop(
    node_id: NodeID,
    node_id_not_found: NodeID,
    node_id_manual_intervention: NodeID,
    is_legacy: bool,
    fake_director_v0_base_url: str,
    save_state: bool,
) -> Iterator[None]:
    can_save_str = f"{save_state}".lower()
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        request_ok = mock.delete(f"/dynamic_services/{node_id}?can_save={can_save_str}")
        if is_legacy:
            request_ok.respond(
                status.HTTP_307_TEMPORARY_REDIRECT,
                headers={
                    "Location": f"{fake_director_v0_base_url}/fake-service-stop-ok/{node_id}?can_save={can_save_str}"
                },
            )
        else:
            request_ok.respond(status.HTTP_204_NO_CONTENT)

        request_not_found = mock.delete(
            f"/dynamic_services/{node_id_not_found}?can_save={can_save_str}"
        )
        if is_legacy:
            request_not_found.respond(
                status.HTTP_307_TEMPORARY_REDIRECT,
                headers={
                    "Location": f"{fake_director_v0_base_url}/fake-service-stop-not-found/{node_id_not_found}?can_save={can_save_str}"
                },
            )
        else:
            request_not_found.respond(status.HTTP_404_NOT_FOUND)

        request_manual_intervention = mock.delete(
            f"/dynamic_services/{node_id_manual_intervention}?can_save={can_save_str}"
        )
        if is_legacy:
            request_manual_intervention.respond(
                status.HTTP_307_TEMPORARY_REDIRECT,
                headers={
                    "Location": f"{fake_director_v0_base_url}/fake-service-stop-manual/{node_id_manual_intervention}?can_save={can_save_str}"
                },
            )
        else:
            request_manual_intervention.respond(status.HTTP_409_CONFLICT)

        yield None


@pytest.mark.parametrize("is_legacy", [True, False])
@pytest.mark.parametrize("save_state", [True, False])
async def test_stop_dynamic_service(
    mock_director_v0_service_stop: None,
    mock_director_v2_service_stop: None,
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    node_id_not_found: NodeID,
    node_id_manual_intervention: NodeID,
    simcore_user_agent: str,
    save_state: bool,
):
    def _get_rpc_stop(with_node_id: NodeID) -> DynamicServiceStop:
        return DynamicServiceStop(
            user_id=user_id,
            project_id=project_id,
            node_id=with_node_id,
            simcore_user_agent=simcore_user_agent,
            save_state=save_state,
        )

    # service was stopped
    result = await services.stop_dynamic_service(
        rpc_client,
        dynamic_service_stop=_get_rpc_stop(node_id),
        timeout_s=5,
    )
    assert result is None

    # service was not found
    with pytest.raises(ServiceWasNotFoundError):
        await services.stop_dynamic_service(
            rpc_client,
            dynamic_service_stop=_get_rpc_stop(node_id_not_found),
            timeout_s=5,
        )

    # service awaits for manual intervention
    with pytest.raises(ServiceWaitingForManualInterventionError):
        await services.stop_dynamic_service(
            rpc_client,
            dynamic_service_stop=_get_rpc_stop(node_id_manual_intervention),
            timeout_s=5,
        )


@pytest.fixture
def mock_raise_generic_error(
    mocker: MockerFixture,
) -> None:
    module_base = (
        "simcore_service_dynamic_scheduler.services.director_v2._public_client"
    )
    mocker.patch(
        f"{module_base}.DirectorV2Client.stop_dynamic_service",
        autospec=True,
        side_effect=Exception("raised as expected"),
    )


@pytest.mark.parametrize("save_state", [True, False])
async def test_stop_dynamic_service_serializes_generic_errors(
    mock_raise_generic_error: None,
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
):
    with pytest.raises(
        RPCServerError, match="While running method 'stop_dynamic_service'"
    ):
        await services.stop_dynamic_service(
            rpc_client,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                simcore_user_agent=simcore_user_agent,
                save_state=save_state,
            ),
            timeout_s=5,
        )
