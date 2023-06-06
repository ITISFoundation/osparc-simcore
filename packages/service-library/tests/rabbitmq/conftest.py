import datetime
import time
from typing import AsyncIterator, Coroutine, cast

import aiodocker
import pytest


@pytest.fixture
async def cleanup_check_rabbitmq_server_has_no_errors() -> AsyncIterator[None]:
    now = datetime.datetime.now()
    yield
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
                since=time.mktime(now.timetuple()),
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
    assert not filtered_warning_logs
    assert not error_logs
    print("<-- no error founds in rabbitmq server logs, that's great. good job!")
