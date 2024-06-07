import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm import SSMClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimcoreSSMAPI:
    client: SSMClient
    session: aioboto3.Session
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    async def create(cls, settings: SSMSettings) -> "SimcoreSSMAPI":
        session = aioboto3.Session()
        session_client = session.client(
            "ssm",
            endpoint_url=settings.SSM_ENDPOINT,
            aws_access_key_id=settings.SSM_ACCESS_KEY_ID,
            aws_secret_access_key=settings.SSM_SECRET_ACCESS_KEY,
            region_name=settings.SSM_REGION_NAME,
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        exit_stack = contextlib.AsyncExitStack()
        ec2_client = cast(
            SSMClient, await exit_stack.enter_async_context(session_client)
        )
        return cls(ec2_client, session, exit_stack)

    async def close(self) -> None:
        await self.exit_stack.aclose()

    async def ping(self) -> bool:
        try:
            await self.client.list_commands(MaxResults=1)
            return True
        except Exception:  # pylint: disable=broad-except
            return False
