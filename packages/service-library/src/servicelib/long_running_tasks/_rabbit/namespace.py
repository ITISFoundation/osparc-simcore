from models_library.rabbitmq_basic_types import RPCNamespace
from pydantic import TypeAdapter

from ..models import RabbitNamespace


def get_namespace(namespace: RabbitNamespace) -> RPCNamespace:
    return TypeAdapter(RPCNamespace).validate_python(f"lrt-{namespace}")
