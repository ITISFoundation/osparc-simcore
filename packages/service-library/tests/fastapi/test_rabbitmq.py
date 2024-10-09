# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import AsyncIterable, Callable

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage, RabbitMessageBase
from pydantic import ValidationError
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.rabbitmq import get_rabbitmq_client, setup_rabbit
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient
from settings_library.rabbit import RabbitSettings
from tenacity import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def rabbit_log_message(faker: Faker) -> LoggerRabbitMessage:
    return LoggerRabbitMessage(
        user_id=faker.pyint(min_value=1),
        project_id=faker.uuid4(),
        node_id=faker.uuid4(),
        messages=faker.pylist(allowed_types=(str,)),
    )


@pytest.fixture(params=["rabbit_log_message"])
def rabbit_message(
    request: pytest.FixtureRequest,
    rabbit_log_message: LoggerRabbitMessage,
) -> RabbitMessageBase:
    return {
        "rabbit_log_message": rabbit_log_message,
    }[request.param]


@pytest.fixture
def disabled_rabbitmq(
    rabbit_env_vars_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    for key in rabbit_env_vars_dict:
        rabbit_env_vars_dict[key] = "null"
    setenvs_from_dict(monkeypatch, rabbit_env_vars_dict)


@pytest.fixture
def enabled_rabbitmq(
    rabbit_env_vars_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> RabbitSettings:
    setenvs_from_dict(monkeypatch, rabbit_env_vars_dict)
    return RabbitSettings.create_from_envs()


@pytest.fixture
async def initialized_app(app: FastAPI, is_pdb_enabled: bool) -> AsyncIterable[FastAPI]:
    rabbit_settings: RabbitSettings | None = None
    try:
        rabbit_settings = RabbitSettings.create_from_envs()
        setup_rabbit(app=app, settings=rabbit_settings, name="my_rabbitmq_client")
    except ValidationError:
        pass
    async with LifespanManager(
        app=app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        yield app


def test_rabbitmq_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    initialized_app: FastAPI,
):
    with pytest.raises(AttributeError):
        get_rabbitmq_client(initialized_app)


def test_rabbitmq_initializes(
    enabled_rabbitmq: RabbitSettings,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "rabbitmq_client")
    assert initialized_app.state.rabbitmq_client is not None
    assert get_rabbitmq_client(initialized_app) == initialized_app.state.rabbitmq_client


async def test_post_message(
    enabled_rabbitmq: RabbitSettings,
    initialized_app: FastAPI,
    rabbit_message: RabbitMessageBase,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocker: MockerFixture,
):
    mocked_message_handler = mocker.AsyncMock(return_value=True)
    consumer_rmq = create_rabbitmq_client("pytest_consumer")
    await consumer_rmq.subscribe(
        rabbit_message.channel_name,
        mocked_message_handler,
        topics=[BIND_TO_ALL_TOPICS] if rabbit_message.routing_key() else None,
    )

    producer_rmq = get_rabbitmq_client(initialized_app)
    assert producer_rmq is not None
    await producer_rmq.publish(rabbit_message.channel_name, rabbit_message)

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            print(
                f"--> checking for message in rabbit exchange {rabbit_message.channel_name}, {attempt.retry_state.retry_object.statistics}"
            )
            mocked_message_handler.assert_called_once_with(
                rabbit_message.model_dump_json().encode()
            )
            print("... message received")
