import distributed
import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    # configured as worker
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "DASK_WORKER_RABBITMQ": rabbit_service.model_dump_json(),
        },
    )
    return app_environment | envs


def test_rabbitmq_plugin_initializes(dask_client: distributed.Client): ...
