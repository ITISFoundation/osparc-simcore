# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from faker import Faker
from models_library.rabbitmq_messages import LoggerRabbitMessage, RabbitMessageBase
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


# # https://github.com/ITISFoundation/osparc-simcore/issues/5059
# def test_rabbitmq_does_not_initialize_if_deactivated(
#     disabled_rabbitmq: None,
#     initialized_app: FastAPI,
# ):
#     assert hasattr(initialized_app.state, "rabbitmq_client")
#     assert initialized_app.state.rabbitmq_client is None
#     with pytest.raises(InvalidConfig):
#         get_rabbitmq_client(initialized_app)

# def test_rabbitmq_initializes(
#     enabled_rabbitmq: RabbitSettings,
#     initialized_app: FastAPI,
# ):
#     assert hasattr(initialized_app.state, "rabbitmq_client")
#     assert initialized_app.state.rabbitmq_client is not None
#     assert (
#         get_rabbitmq_client(initialized_app)
#         == initialized_app.state.rabbitmq_client
#     )

# async def test_post_message(
#     enabled_rabbitmq: RabbitSettings,
#     initialized_app: FastAPI,
#     rabbit_message: RabbitMessageBase,
#     create_rabbitmq_client: Callable[[str], RabbitMQClient],
#     mocker: MockerFixture,
# ):
#     mocked_message_handler = mocker.AsyncMock(return_value=True)
#     consumer_rmq = create_rabbitmq_client("pytest_consumer")
#     await consumer_rmq.subscribe(
#         rabbit_message.channel_name,
#         mocked_message_handler,
#         topics=[BIND_TO_ALL_TOPICS] if rabbit_message.routing_key() else None,
#     )

#     producer_rmq = get_rabbitmq_client(initialized_app)
#     assert producer_rmq is not None
#     await producer_rmq.publish(rabbit_message.channel_name, rabbit_message)

#     async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
#         with attempt:
#             print(
#                 f"--> checking for message in rabbit exchange {rabbit_message.channel_name}, {attempt.retry_state.retry_object.statistics}"
#             )
#             mocked_message_handler.assert_called_once_with(
#                 rabbit_message.json().encode()
#             )
#             print("... message received")

# async def test_post_message_with_disabled_rabbit_does_not_raise(
#     disabled_rabbitmq: None,
#     disabled_ec2: None,
#     mocked_redis_server: None,
#     initialized_app: FastAPI,
#     rabbit_message: RabbitMessageBase,
# ):
#     await post_message(initialized_app, message=rabbit_message)

# async def _switch_off_rabbit_mq_instance(
#     async_docker_client: aiodocker.Docker,
# ) -> None:
#     # remove the rabbit MQ instance
#     rabbit_services = [
#         s
#         for s in await async_docker_client.services.list()
#         if "rabbit" in s["Spec"]["Name"]
#     ]
#     await asyncio.gather(
#         *(async_docker_client.services.delete(s["ID"]) for s in rabbit_services)
#     )

#     @retry(**_TENACITY_RETRY_PARAMS)
#     async def _check_service_task_gone(service: Mapping[str, Any]) -> None:
#         print(
#             f"--> checking if service {service['ID']}:{service['Spec']['Name']} is really gone..."
#         )
#         list_of_tasks = await async_docker_client.containers.list(
#             all=True,
#             filters={
#                 "label": [f"com.docker.swarm.service.id={service['ID']}"],
#             },
#         )
#         assert not list_of_tasks
#         print(f"<-- service {service['ID']}:{service['Spec']['Name']} is gone.")

#     await asyncio.gather(*(_check_service_task_gone(s) for s in rabbit_services))

# async def test_post_message_when_rabbit_disconnected(
#     enabled_rabbitmq: RabbitSettings,
#     disabled_ec2: None,
#     mocked_redis_server: None,
#     initialized_app: FastAPI,
#     rabbit_log_message: LoggerRabbitMessage,
#     async_docker_client: aiodocker.Docker,
# ):
#     await _switch_off_rabbit_mq_instance(async_docker_client)

#     # now posting should not raise out
#     await post_message(initialized_app, message=rabbit_log_message)
