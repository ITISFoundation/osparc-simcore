import contextlib
import logging
from dataclasses import dataclass
from typing import Optional, cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from fastapi import FastAPI
from types_aiobotocore_ec2 import EC2Client

from ..core.errors import ConfigurationError
from ..core.settings import EC2Settings

logger = logging.getLogger(__name__)


@dataclass
class AutoscalingEC2:
    client: EC2Client
    session: aioboto3.Session
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    async def create(cls, settings: EC2Settings) -> "AutoscalingEC2":
        session = aioboto3.Session()
        session_client = session.client(
            "ec2",
            endpoint_url=settings.EC2_ENDPOINT,
            aws_access_key_id=settings.EC2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.EC2_SECRET_ACCESS_KEY,
            region_name=settings.EC2_REGION_NAME,
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        exit_stack = contextlib.AsyncExitStack()
        ec2_client = cast(
            EC2Client, await exit_stack.enter_async_context(session_client)
        )
        return cls(ec2_client, session, exit_stack)

    async def close(self) -> None:
        await self.exit_stack.aclose()


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.ec2_client = None
        settings: Optional[EC2Settings] = app.state.settings.EC2Settings
        if not settings:
            logger.warning("EC2 client is de-activated in the settings")
            return

        app.state.ec2_client = await AutoscalingEC2.create(settings)

    async def on_shutdown() -> None:
        if app.state.ec2_client:
            await cast(AutoscalingEC2, app.state.ec2_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_ec2_client(app: FastAPI) -> EC2Client:
    if not app.state.ec2_client:
        raise ConfigurationError(
            msg="EC2 client is not available. Please check the configuration."
        )
    return cast(AutoscalingEC2, app.state.ec2_client).client
