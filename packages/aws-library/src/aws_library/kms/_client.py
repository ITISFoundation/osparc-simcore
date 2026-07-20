import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from servicelib.logging_utils import log_decorator
from settings_library.kms import KMSSettings
from types_aiobotocore_kms import KMSClient

from ._error_handler import kms_exception_handler

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimcoreKMSAPI:
    _client: KMSClient
    _session: aioboto3.Session
    _exit_stack: contextlib.AsyncExitStack
    _default_key_id: str

    @classmethod
    async def create(cls, settings: KMSSettings) -> "SimcoreKMSAPI":
        session = aioboto3.Session()
        session_client_kwargs = {
            "endpoint_url": settings.KMS_ENDPOINT,
            "region_name": settings.KMS_REGION_NAME,
        }
        if settings.KMS_ACCESS_KEY_ID and settings.KMS_SECRET_ACCESS_KEY:
            session_client_kwargs["aws_access_key_id"] = settings.KMS_ACCESS_KEY_ID.get_secret_value()
            session_client_kwargs["aws_secret_access_key"] = settings.KMS_SECRET_ACCESS_KEY.get_secret_value()
        # NOTE: if no static credentials are provided, aioboto3/botocore falls back
        # to the default AWS credentials chain (e.g. EC2/ECS instance IAM role)
        session_client = session.client("kms", **session_client_kwargs)
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        exit_stack = contextlib.AsyncExitStack()
        kms_client = cast(KMSClient, await exit_stack.enter_async_context(session_client))
        return cls(kms_client, session, exit_stack, settings.KMS_KEY_ID)

    async def close(self) -> None:
        await self._exit_stack.aclose()

    async def ping(self) -> bool:
        try:
            await self._client.describe_key(KeyId=self._default_key_id)
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    @log_decorator(_logger, logging.DEBUG)
    @kms_exception_handler(_logger)
    async def encrypt(
        self,
        plaintext: bytes,
        *,
        key_id: str | None = None,
        encryption_context: dict[str, str] | None = None,
    ) -> bytes:
        """Encrypts ``plaintext`` (e.g. a job root key) using the configured KMS key.

        Raises:
            KMSAccessError:
        """
        response = await self._client.encrypt(
            KeyId=key_id or self._default_key_id,
            Plaintext=plaintext,
            EncryptionContext=encryption_context or {},
        )
        return response["CiphertextBlob"]

    @log_decorator(_logger, logging.DEBUG)
    @kms_exception_handler(_logger)
    async def decrypt(
        self,
        ciphertext: bytes,
        *,
        key_id: str | None = None,
        encryption_context: dict[str, str] | None = None,
    ) -> bytes:
        """Decrypts a ``ciphertext`` blob previously produced by :meth:`encrypt`.

        Raises:
            KMSAccessError:
        """
        response = await self._client.decrypt(
            KeyId=key_id or self._default_key_id,
            CiphertextBlob=ciphertext,
            EncryptionContext=encryption_context or {},
        )
        return response["Plaintext"]
