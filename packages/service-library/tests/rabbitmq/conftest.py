from collections.abc import AsyncIterator, Callable, Coroutine
from typing import cast

import aiodocker
import arrow
import pytest
from faker import Faker


@pytest.fixture(autouse=True)
async def cleanup_check_rabbitmq_server_has_no_errors(
    request: pytest.FixtureRequest,
) -> AsyncIterator[None]:
    now = arrow.utcnow()
    yield
    if "no_cleanup_check_rabbitmq_server_has_no_errors" in request.keywords:
        return
    print("--> checking for errors/warnings in rabbitmq logs...")
    async with aiodocker.Docker() as docker_client:
        containers = await docker_client.containers.list(filters=({"name": ["rabbit"]}))
        assert len(containers) == 1, "missing rabbit container!"
        rabbit_container = containers[0]

        all_logs = await cast(
            Coroutine,
            rabbit_container.log(
                stdout=True,
                stderr=True,
                follow=False,
                since=now.timestamp(),
            ),
        )

    warning_logs = [log for log in all_logs if "warning" in log]
    error_logs = [log for log in all_logs if "error" in log]
    RABBIT_SKIPPED_WARNINGS = [
        "rebuilding indices from scratch",
    ]
    filtered_warning_logs = [
        log
        for log in warning_logs
        if all(w not in log for w in RABBIT_SKIPPED_WARNINGS)
    ]
    assert (
        not filtered_warning_logs
    ), f"warning(s) found in rabbitmq logs for {request.function}"
    assert not error_logs, f"error(s) found in rabbitmq logs for {request.function}"
    print("<-- no error founds in rabbitmq server logs, that's great. good job!")


@pytest.fixture
def random_exchange_name() -> Callable[[], str]:
    def _creator() -> str:
        faker = (
            Faker()
        )  # NOTE: this ensure the faker seed is new each time, since we do not clean the exchanges
        return f"pytest_fake_exchange_{faker.pystr()}"

    return _creator
