from ._client import SimcoreKMSAPI
from ._errors import (
    KMSAccessError,
    KMSInvalidCiphertextError,
    KMSKeyNotFoundError,
    KMSNotConnectedError,
    KMSRuntimeError,
)
from ._fastapi_lifespan import configure_kms_client

__all__: tuple[str, ...] = (
    "KMSAccessError",
    "KMSInvalidCiphertextError",
    "KMSKeyNotFoundError",
    "KMSNotConnectedError",
    "KMSRuntimeError",
    "SimcoreKMSAPI",
    "configure_kms_client",
)
