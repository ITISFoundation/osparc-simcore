import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final
from uuid import uuid4

from pydantic import NonNegativeInt
from servicelib.deferred_tasks import (
    BaseDeferredHandler,
    DeferredManager,
    FullStartContext,
    TaskUID,
    UserStartContext,
)
from servicelib.redis import RedisClientSDK, RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings

_CONSTANT_RESULT: Final[str] = "always_the_same"


class ExampleDeferredHandler(BaseDeferredHandler[str]):
    @classmethod
    async def get_timeout(cls, start_context: FullStartContext) -> timedelta:
        return timedelta(seconds=60)

    @classmethod
    async def start_deferred(cls, sleep_duration: float) -> UserStartContext:
        return {"sleep_duration": sleep_duration}

    @classmethod
    async def on_deferred_created(
        cls, task_uid: TaskUID, start_context: FullStartContext
    ) -> None:
        distributed_lists: DistributedLists = start_context["distributed_lists"]
        await distributed_lists.append_to("scheduled", task_uid)

    @classmethod
    async def run_deferred(cls, start_context: FullStartContext) -> str:
        sleep_duration: float = start_context["sleep_duration"]
        await asyncio.sleep(sleep_duration)
        return _CONSTANT_RESULT

    @classmethod
    async def on_deferred_result(
        cls, result: str, start_context: FullStartContext
    ) -> None:
        distributed_lists: DistributedLists = start_context["distributed_lists"]
        await distributed_lists.append_to("results", result)


class DistributedLists:
    def __init__(self, redis_settings: RedisSettings) -> None:
        self.redis_sdk = RedisClientSDK(
            redis_settings.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
        )

    def _get_queue_name(self, queue_name: str) -> str:
        return f"distributed_lists::{queue_name}"

    async def append_to(self, queue_name: str, value: Any) -> None:
        await self.redis_sdk.redis.rpush(self._get_queue_name(queue_name), value)  # type: ignore

    async def get_all_from(self, queue_name: str) -> list:
        return await self.redis_sdk.redis.lrange(
            self._get_queue_name(queue_name), 0, -1
        )  # type: ignore


class ExampleApp:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        distributed_lists: DistributedLists,
        max_workers: NonNegativeInt,
    ) -> None:
        self._redis_client = RedisClientSDKHealthChecked(
            redis_settings.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
        )
        self._manager = DeferredManager(
            rabbit_settings,
            self._redis_client,
            globals_for_start_context={"distributed_lists": distributed_lists},
            max_workers=max_workers,
        )

    async def setup(self) -> None:
        await self._redis_client.setup()
        await self._manager.setup()


@dataclass
class Context:
    redis_settings: RedisSettings | None = None
    rabbit_settings: RabbitSettings | None = None
    example_app: ExampleApp | None = None
    distributed_lists: DistributedLists | None = None


async def _commands_handler(
    context: Context, command: str, payload: dict[str, Any]
) -> Any:
    """Handles all commands send by remote party"""
    if command == "init-context":
        context.redis_settings = RedisSettings.parse_raw(payload["redis"])
        context.rabbit_settings = RabbitSettings.parse_raw(payload["rabbit"])
        # using the same db as the deferred tasks with different keys
        context.distributed_lists = DistributedLists(context.redis_settings)

        context.example_app = ExampleApp(
            context.rabbit_settings,
            context.redis_settings,
            context.distributed_lists,
            payload["max-workers"],
        )
        await context.example_app.setup()

        print(f"Initialized context {context=}")

        return None

    if command == "start":
        await ExampleDeferredHandler.start_deferred(**payload)
        return None

    if command == "get-scheduled":
        assert context.distributed_lists
        return await context.distributed_lists.get_all_from("scheduled")

    if command == "get-results":
        assert context.distributed_lists
        return await context.distributed_lists.get_all_from("results")

    return None


class AsyncTCPServer:
    def __init__(
        self, host: str = "127.0.0.1", port: int = 3562, buff_size: int = 10000
    ) -> None:
        self.host = host
        self.port = port
        self.buff_size = buff_size

        self._scheduled: list = []
        self._results: list = []

        self._context = Context()

    async def _handle_request(self, command: Any) -> Any:
        unique_request_id = uuid4()
        print(f"[{unique_request_id}] request:  {command=}")
        response = await _commands_handler(
            self._context, command["command"], command["payload"]
        )
        print(f"[{unique_request_id}] response: {response=}")
        return response

    async def _handle_client(self, reader, writer):
        while True:
            data = await reader.read(self.buff_size)
            if not data:
                break
            response = await self._handle_request(json.loads(data.decode()))
            writer.write(json.dumps(response).encode())
            await writer.drain()

        print("Client disconnected.")
        writer.close()

    async def run(self):
        # disable
        tcp_server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        addr = tcp_server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        async with tcp_server:
            await tcp_server.serve_forever()


if __name__ == "__main__":
    asyncio.run(AsyncTCPServer().run())
