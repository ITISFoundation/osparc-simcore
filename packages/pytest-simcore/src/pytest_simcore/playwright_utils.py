import json
from dataclasses import dataclass
from typing import Any, Final

SECOND: Final[int] = 1000
MINUTE: Final[int] = 60 * SECOND


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoRegisteredUser:
    user_email: str
    password: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]


def decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix("42"))
    return SocketIOEvent(name=data[0], obj=json.loads(data[1]))


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_states: tuple[str, ...]

    def __call__(self, message: str) -> bool:
        # print(f"<---- received websocket {message=}")
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith("42"):
            decoded_message = decode_socketio_42_message(message)
            if decoded_message.name == "projectStateUpdated":
                return (
                    decoded_message.obj["data"]["state"]["value"]
                    in self.expected_states
                )

        return False
