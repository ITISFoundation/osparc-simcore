import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm import SSMClient
from types_aiobotocore_ssm.literals import CommandStatusType

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SSMCommand:
    name: str
    command_id: str
    instance_id: str
    status: CommandStatusType


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

    # a function to send a command via ssm
    async def send_command(
        self, instance_id: str, command: str, command_name: str
    ) -> SSMCommand:
        # TODO: evaluate using Targets instead of instances as this is limited to 50 instances
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.send_command
        response = await self.client.send_command(
            InstanceIds=tuple(
                instance_id,
            ),
            DocumentName="AWS-RunShellScript",
            Comment=command_name,
            Parameters={"commands": [command]},
        )
        assert response["Command"]  # nosec
        assert "Comment" in response["Command"]  # nosec
        assert "CommandId" in response["Command"]  # nosec
        assert "Status" in response["Command"]  # nosec

        return SSMCommand(
            name=response["Command"]["Comment"],
            command_id=response["Command"]["CommandId"],
            status=response["Command"]["Status"],
            instance_id=instance_id,
        )

    # a function to list commands on an instance
    async def list_commands_on_instance(self, instance_id: str) -> list[SSMCommand]:
        response = await self.client.list_commands(
            InstanceId=instance_id, MaxResults=100
        )
        return [
            SSMCommand(
                name=command["Comment"],
                command_id=command["CommandId"],
                status=command["Status"],
                instance_id=instance_id,
            )
            for command in response["Commands"]
            if all(_ in command for _ in ("Comment", "CommandId", "Status"))
        ]
