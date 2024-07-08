import contextlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from servicelib.logging_utils import log_decorator
from settings_library.ssm import SSMSettings
from types_aiobotocore_ssm import SSMClient
from types_aiobotocore_ssm.literals import CommandStatusType

from ._error_handler import ssm_exception_handler
from ._errors import SSMCommandExecutionError

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SSMCommand:
    name: str
    command_id: str
    instance_ids: Sequence[str]
    status: CommandStatusType
    message: str | None = None


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
    @log_decorator(_logger, logging.DEBUG)
    @ssm_exception_handler(_logger)
    async def send_command(
        self, instance_ids: Sequence[str], *, command: str, command_name: str
    ) -> SSMCommand:
        # NOTE: using Targets instead of instances as this is limited to 50 instances
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html#SSM.Client.send_command
        response = await self.client.send_command(
            Targets=[{"Key": "InstanceIds", "Values": instance_ids}],
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
            instance_ids=instance_ids,
        )

    @log_decorator(_logger, logging.DEBUG)
    @ssm_exception_handler(_logger)
    async def get_command(self, instance_id: str, *, command_id: str) -> SSMCommand:

        response = await self.client.get_command_invocation(
            CommandId=command_id, InstanceId=instance_id
        )

        return SSMCommand(
            name=response["Comment"],
            command_id=response["CommandId"],
            instance_ids=[response["InstanceId"]],
            status=response["Status"] if response["Status"] != "Delayed" else "Pending",
            message=response["StatusDetails"],
        )

    @log_decorator(_logger, logging.DEBUG)
    @ssm_exception_handler(_logger)
    async def is_instance_connected_to_ssm_server(self, instance_id: str) -> bool:
        response = await self.client.describe_instance_information(
            InstanceInformationFilterList=[
                {
                    "key": "InstanceIds",
                    "valueSet": [
                        instance_id,
                    ],
                }
            ],
        )
        assert response["InstanceInformationList"]  # nosec
        assert len(response["InstanceInformationList"]) == 1  # nosec
        assert "PingStatus" in response["InstanceInformationList"][0]  # nosec
        return bool(response["InstanceInformationList"][0]["PingStatus"] == "Online")

    @log_decorator(_logger, logging.DEBUG)
    @ssm_exception_handler(_logger)
    async def wait_for_has_instance_completed_cloud_init(
        self, instance_id: str
    ) -> bool:
        cloud_init_status_command = await self.send_command(
            (instance_id,),
            command="cloud-init status",
            command_name="cloud-init status",
        )
        # wait for command to complete
        waiter = self.client.get_waiter("command_executed")
        await waiter.wait(
            CommandId=cloud_init_status_command.command_id, InstanceId=instance_id
        )
        response = await self.client.get_command_invocation(
            CommandId=cloud_init_status_command.command_id, InstanceId=instance_id
        )
        if response["Status"] != "Success":
            raise SSMCommandExecutionError(details=response["StatusDetails"])
        # check if cloud-init is done
        return bool(response["StandardOutputContent"] == "status: done\n")
