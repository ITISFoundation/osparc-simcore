# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from collections.abc import AsyncIterator
from typing import Final

import pytest
import tenacity
from fakeredis import FakeAsyncRedis
from pydantic import SecretStr, TypeAdapter
from pytest_mock import MockerFixture
from redis.asyncio import Redis, from_url
from servicelib.redis import handle_redis_returns_union_types
from settings_library.basic_types import PortInt
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.logging_tools import log_context
from .helpers.typing_env import EnvVarsDict
from .helpers.valkey_tools import get_valkey_databases_count
from .helpers.xdist import get_worker_id, is_xdist_worker

log = logging.getLogger(__name__)

# one bank of this many logical databases per xdist worker on the shared valkey container.
# The docker_stack fixture widens `--databases` in the generated (test-only) compose to fit
# every worker's bank, so this number and the deployed count never need manual syncing.
_NUM_LOGICAL_REDIS_DATABASES: Final[int] = len(RedisDatabase)


def _worker_db_offset(request: pytest.FixtureRequest, deployed_databases_count: int) -> int:
    # under xdist, each worker reserves its own bank of `_NUM_LOGICAL_REDIS_DATABASES` indices
    # on the SAME shared redis/valkey container, so the app-under-test's own redis usage
    # (locks, pubsub, ...) never collides with another worker's
    if not is_xdist_worker(request):
        return 0
    worker_id = get_worker_id(request)
    digits = "".join(ch for ch in worker_id if ch.isdigit())
    worker_ordinal = int(digits) if digits else 0
    offset = (worker_ordinal + 1) * _NUM_LOGICAL_REDIS_DATABASES
    # `--databases` is boot-time only: a stack deployed from a stale compose (e.g. kept alive
    # across runs with --keep-docker-up) cannot be widened while running -> fail with the
    # exact remedies instead of confusing "DB index out of range" errors at test runtime
    assert offset + _NUM_LOGICAL_REDIS_DATABASES <= deployed_databases_count, (
        f"xdist worker '{worker_id}' needs redis databases [{offset}, "
        f"{offset + _NUM_LOGICAL_REDIS_DATABASES - 1}] but the deployed valkey only has "
        f"{deployed_databases_count}. Tear the stack down and let it re-deploy with the "
        f"widened `--databases` (a stale stack kept up by --keep-docker-up still runs the old "
        f"count), or reduce the number of xdist workers (-n)."
    )
    return offset


@pytest.fixture
async def redis_settings(
    docker_stack: dict,  # stack is up
    env_vars_for_docker_compose: EnvVarsDict,
    request: pytest.FixtureRequest,
) -> RedisSettings:
    """Returns the settings of a redis service that is up and responsive"""

    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_redis" in docker_stack["services"]

    db_offset = 0
    if is_xdist_worker(request):
        # only xdist workers remap onto a per-worker bank of logical databases, which requires
        # the deployed valkey to have been widened with `--databases` (see `_worker_db_offset`).
        # A non-xdist run uses offset 0, so it must NOT read the (possibly redis-less, when the
        # current module did not select redis) module-scoped compose here.
        deployed_compose = docker_stack["stacks"]["core"]["compose"]
        deployed_databases_count = get_valkey_databases_count(deployed_compose)
        assert deployed_databases_count is not None, "deployed redis/valkey service has no --databases?"
        db_offset = _worker_db_offset(request, deployed_databases_count)

    port = get_service_published_port("simcore_redis", int(env_vars_for_docker_compose["REDIS_PORT"]))
    # test runner is running on the host computer
    settings = RedisSettings(
        REDIS_HOST=get_localhost_ip(),
        REDIS_PORT=TypeAdapter(PortInt).validate_python(port),
        REDIS_PASSWORD=SecretStr(env_vars_for_docker_compose["REDIS_PASSWORD"]),
        REDIS_DB_OFFSET=db_offset,
    )
    with log_context(
        logging.INFO,
        f"waiting for redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} "
        f"(db offset {settings.REDIS_DB_OFFSET}) to be responsive",
        logger=log,
    ):
        await wait_till_redis_responsive(settings.build_redis_dsn(RedisDatabase.RESOURCES))

    return settings


@pytest.fixture()
def redis_service(
    redis_settings: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> RedisSettings:
    """Sets env vars for a redis service is up and responsive and returns its settings as well

    NOTE: Use this fixture to setup client app
    """
    monkeypatch.setenv("REDIS_HOST", redis_settings.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", str(redis_settings.REDIS_PORT))
    monkeypatch.setenv(
        "REDIS_PASSWORD", redis_settings.REDIS_PASSWORD.get_secret_value() if redis_settings.REDIS_PASSWORD else "null"
    )
    monkeypatch.setenv("REDIS_DB_OFFSET", str(redis_settings.REDIS_DB_OFFSET))
    return redis_settings


@pytest.fixture()
async def redis_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = from_url(
        redis_settings.build_redis_dsn(RedisDatabase.RESOURCES),
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    # NOTE: flushdb (not flushall) - only clears the db actually used by this fixture/worker
    await client.flushdb()
    await client.aclose(close_connection_pool=True)


@pytest.fixture()
async def redis_locks_client(
    redis_settings: RedisSettings,
) -> AsyncIterator[Redis]:
    """Creates a redis client to communicate with a redis service ready"""
    client = from_url(
        redis_settings.build_redis_dsn(RedisDatabase.LOCKS),
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    # NOTE: flushdb (not flushall) - only clears the db actually used by this fixture/worker
    await client.flushdb()
    await client.aclose(close_connection_pool=True)


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(60),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
async def wait_till_redis_responsive(redis_url: URL | str) -> None:
    client = from_url(f"{redis_url}", encoding="utf-8", decode_responses=True)
    try:
        # NOTE: redis' sync/async shared command typings return `bool | Awaitable[bool]`,
        # hence the helper (same as servicelib.redis.RedisClientSDK.ping)
        if not await handle_redis_returns_union_types(client.ping()):
            msg = f"{redis_url=} not available"
            raise ConnectionError(msg)
    finally:
        await client.aclose(close_connection_pool=True)


@pytest.fixture
async def use_in_memory_redis(mocker: MockerFixture) -> RedisSettings:
    mocker.patch("redis.asyncio.from_url", FakeAsyncRedis)
    return RedisSettings()
