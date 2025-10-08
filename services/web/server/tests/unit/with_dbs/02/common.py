from typing import TypedDict
from unittest import mock


class SocketHandlers(TypedDict):
    SOCKET_IO_PROJECT_UPDATED_EVENT: mock.Mock
