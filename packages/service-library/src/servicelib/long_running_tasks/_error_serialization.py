import base64
import logging
import pickle
from abc import ABC, abstractmethod
from typing import Final, Generic, TypeVar

_logger = logging.getLogger(__name__)


T = TypeVar("T")


class BaseObjectSerializer(ABC, Generic[T]):

    @classmethod
    @abstractmethod
    def get_init_kwargs_from_object(cls, obj: T) -> dict:
        """dictionary reppreseting the kwargs passed to the __init__ method"""

    @classmethod
    @abstractmethod
    def prepare_object_init_kwargs(cls, data: dict) -> dict:
        """cleanup data to be used as kwargs for the __init__ method if required"""


_SERIALIZERS: Final[dict[type, type[BaseObjectSerializer]]] = {}


def register_custom_serialization(
    object_type: type, object_serializer: type[BaseObjectSerializer]
) -> None:
    """Register a custom serializer for a specific object type.

    Arguments:
        object_type -- the type or parent class of the object to be serialized
        object_serializer -- custom implementation of BaseObjectSerializer for the object type
    """
    _SERIALIZERS[object_type] = object_serializer


_TYPE_FIELD: Final[str] = "__pickle__type__field__"
_MODULE_FIELD: Final[str] = "__pickle__module__field__"


def error_to_string(e: Exception) -> str:
    """Serialize exception to base64-encoded string."""
    to_serialize: Exception | dict = e
    object_class = type(e)

    for registered_class, object_serializer in _SERIALIZERS.items():
        if issubclass(object_class, registered_class):
            to_serialize = {
                _TYPE_FIELD: type(e).__name__,
                _MODULE_FIELD: type(e).__module__,
                **object_serializer.get_init_kwargs_from_object(e),
            }
            break

    return base64.b85encode(pickle.dumps(to_serialize)).decode("utf-8")


def error_from_string(error_str: str) -> Exception:
    """Deserialize exception from base64-encoded string."""
    data = pickle.loads(base64.b85decode(error_str))  # noqa: S301

    if isinstance(data, dict) and _TYPE_FIELD in data and _MODULE_FIELD in data:
        try:
            # Import the module and get the exception class
            module = __import__(data[_MODULE_FIELD], fromlist=[data[_TYPE_FIELD]])
            exception_class = getattr(module, data[_TYPE_FIELD])

            for registered_class, object_serializer in _SERIALIZERS.items():
                if issubclass(exception_class, registered_class):
                    # remove unrequired
                    data.pop(_TYPE_FIELD)
                    data.pop(_MODULE_FIELD)

                    return exception_class(  # type: ignore[no-any-return]
                        **object_serializer.prepare_object_init_kwargs(data)
                    )
        except (ImportError, AttributeError, TypeError) as e:
            msg = f"Could not reconstruct object from data: {data}"
            raise ValueError(msg) from e

    return data  # type: ignore[no-any-return]
