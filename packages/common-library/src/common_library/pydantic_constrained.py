from collections.abc import Callable
from typing import Annotated, Any, TypeAlias

from pydantic import Field, TypeAdapter

# https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers#Registered_ports
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]

ValidatedRegisteredPortInt: Callable[[Any], RegisteredPortInt] = TypeAdapter(
    RegisteredPortInt
).validate_python
