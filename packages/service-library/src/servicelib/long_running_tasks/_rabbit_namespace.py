from models_library.rabbitmq_basic_types import RPCNamespace
from pydantic import TypeAdapter

from .models import LRTNamespace


def get_rabbit_namespace(namespace: LRTNamespace) -> RPCNamespace:
    return TypeAdapter(RPCNamespace).validate_python(f"lrt-{namespace}")
