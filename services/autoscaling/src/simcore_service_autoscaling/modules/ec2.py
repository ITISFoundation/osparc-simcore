import contextlib
import logging
from dataclasses import dataclass
from typing import Optional, cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from fastapi import FastAPI
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType
from types_aiobotocore_ec2.type_defs import ReservationTypeDef

from ..core.errors import (
    ConfigurationError,
    Ec2NotConnectedError,
    Ec2TooManyInstancesError,
)
from ..core.settings import EC2InstancesSettings, EC2Settings
from ..models import EC2Instance
from ..utils.ec2 import compose_user_data

InstancePrivateDNSName = str

logger = logging.getLogger(__name__)


def _is_ec2_instance_running(instance: ReservationTypeDef):
    return (
        instance.get("Instances", [{}])[0].get("State", {}).get("Name", "not_running")
        == "running"
    )


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

    async def ping(self) -> bool:
        try:
            await self.client.describe_account_attributes(DryRun=True)
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    async def get_ec2_instance_capabilities(
        self,
        instance_settings: EC2InstancesSettings,
    ) -> list[EC2Instance]:
        instance_types = await self.client.describe_instance_types(
            InstanceTypes=cast(
                list[InstanceTypeType], instance_settings.EC2_INSTANCES_ALLOWED_TYPES
            )
        )

        list_instances: list[EC2Instance] = []
        for instance in instance_types.get("InstanceTypes", []):
            with contextlib.suppress(KeyError):
                list_instances.append(
                    EC2Instance(
                        name=instance["InstanceType"],
                        cpus=instance["VCpuInfo"]["DefaultVCpus"],
                        ram=parse_obj_as(
                            ByteSize, f"{instance['MemoryInfo']['SizeInMiB']}MiB"
                        ),
                    )
                )
        return list_instances

    async def start_aws_instance(
        self,
        instance_settings: EC2InstancesSettings,
        instance_type: InstanceTypeType,
        tags: dict[str, str],
        startup_script: str,
    ) -> InstancePrivateDNSName:
        with log_context(
            logger,
            logging.INFO,
            msg=f"launching AWS instance {instance_type} with {tags=}",
        ):
            # first check the max amount is not already reached
            if current_instances := await self.client.describe_instances(
                Filters=[
                    {"Name": "tag-key", "Values": [tag_key]} for tag_key in tags.keys()
                ]
            ):
                if (
                    len(current_instances.get("Reservations", []))
                    >= instance_settings.EC2_INSTANCES_MAX_INSTANCES
                ) and all(
                    _is_ec2_instance_running(instance)
                    for instance in current_instances["Reservations"]
                ):
                    raise Ec2TooManyInstancesError(
                        num_instances=instance_settings.EC2_INSTANCES_MAX_INSTANCES
                    )

            instances = await self.client.run_instances(
                ImageId=instance_settings.EC2_INSTANCES_AMI_ID,
                MinCount=1,
                MaxCount=1,
                InstanceType=instance_type,
                InstanceInitiatedShutdownBehavior="terminate",
                KeyName=instance_settings.EC2_INSTANCES_KEY_NAME,
                SubnetId=instance_settings.EC2_INSTANCES_SUBNET_ID,
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": tag_key, "Value": tag_value}
                            for tag_key, tag_value in tags.items()
                        ],
                    }
                ],
                UserData=compose_user_data(startup_script),
                SecurityGroupIds=instance_settings.EC2_INSTANCES_SECURITY_GROUP_IDS,
            )
            instance_id = instances["Instances"][0]["InstanceId"]
            logger.info(
                "New instance launched: %s, waiting for it to start now...", instance_id
            )
            # wait for the instance to be in a running state
            # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
            waiter = self.client.get_waiter("instance_exists")
            await waiter.wait(InstanceIds=[instance_id])
            logger.info(
                "instance %s exists now, waiting for running state...", instance_id
            )

            waiter = self.client.get_waiter("instance_running")
            await waiter.wait(InstanceIds=[instance_id])
            logger.info("instance %s is now running", instance_id)

            # NOTE: this is currently deactivated as this makes starting an instance
            # take between 2-4 minutes more and it seems to be responsive much before
            # nevertheless if we get weird errors, this should be activated again!

            # waiter = client.get_waiter("instance_status_ok")
            # await waiter.wait(InstanceIds=[instance_id])
            # logger.info("instance %s status is OK...", instance_id)

            # get the private IP
            instances = await self.client.describe_instances(InstanceIds=[instance_id])
            private_dns_name: str = instances["Reservations"][0]["Instances"][0][
                "PrivateDnsName"
            ]
            logger.info(
                "instance %s is available on %s, happy computing!!",
                instance_id,
                private_dns_name,
            )
            return private_dns_name


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.ec2_client = None
        settings: Optional[EC2Settings] = app.state.settings.AUTOSCALING_EC2_ACCESS

        if not settings:
            logger.warning("EC2 client is de-activated in the settings")
            return

        app.state.ec2_client = client = await AutoscalingEC2.create(settings)

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise Ec2NotConnectedError()

    async def on_shutdown() -> None:
        if app.state.ec2_client:
            await cast(AutoscalingEC2, app.state.ec2_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_ec2_client(app: FastAPI) -> AutoscalingEC2:
    if not app.state.ec2_client:
        raise ConfigurationError(
            msg="EC2 client is not available. Please check the configuration."
        )
    return cast(AutoscalingEC2, app.state.ec2_client)
