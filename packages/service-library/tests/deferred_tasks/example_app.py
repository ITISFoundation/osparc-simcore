import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings


@dataclass
class Context:
    redis_settings: RedisSettings | None = None
    rabbit_settings: RabbitSettings | None = None


async def _commands_handler(context: Context, command: dict[str, Any]) -> None:
    """Handles all commands send by remote party"""
    return command


class AsyncTCPServer:
    def __init__(
        self, host: str = "127.0.0.1", port: int = 3562, buff_size: int = 10000
    ) -> None:
        self.host = host
        self.port = port
        self.buff_size = buff_size

        self._context = Context()

    async def _handle_request(self, command: Any) -> Any:
        unique_request_id = uuid4()
        print(f"[{unique_request_id}] request:  {command=}")
        response = await _commands_handler(self._context, command)
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
        server = await asyncio.start_server(self._handle_client, self.host, self.port)

        addr = server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(AsyncTCPServer().run())
