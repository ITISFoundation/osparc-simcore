#! /usr/bin/env python3

from pathlib import Path

import arrow
import boto3
import parse
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2.service_resource import ServiceResourceInstancesCollection
from rich import print
from rich.table import Table

app = typer.Typer()

tag_key = "dynamic-cluster"
tag_value = "master"


def _get_instance_name(instance) -> str:
    for tag in instance.tags:
        if tag["Key"] == "Name":
            return tag["Value"]
    return "unknown"


def _get_last_heartbeat_since_now(instance) -> str:
    for tag in instance.tags:
        if tag["Key"] == "last_heartbeat":
            time_diff = arrow.get(tag["Value"]) - arrow.utcnow()
            return f"{int(time_diff.total_seconds() / 60)}:{time_diff.total_seconds() % 60}"
    return "999999"


computational_parser = parse.compile(
    "osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
)


def _custom_sort_key(instance):
    # Custom key function for sorting instances
    name = _get_instance_name(instance)
    result = computational_parser.parse(name)

    if result:
        return (
            0 if result["role"] == "manager" else 1,
            result["user_id"],
            result["wallet_id"],
        )
    return name


def _print_instances_details(
    instances: ServiceResourceInstancesCollection,
    *,
    with_name: str,
    computational_row: bool,
    **rich_table_kwargs,
):
    comp_specific_rows = []
    if computational_row:
        comp_specific_rows = ["DaskSchedulerUI", "last heartbeat"]
    table = Table(
        "Instance",
        "publicIP",
        "privateIP",
        "Name",
        "Created",
        "State",
        *comp_specific_rows,
        **rich_table_kwargs,
    )
    filtered_instances = [
        instance for instance in instances if with_name in _get_instance_name(instance)
    ]

    for instance in sorted(
        filtered_instances,
        key=_custom_sort_key,
    ):
        specific = []
        if computational_row:
            specific = [
                f"http://{instance.public_ip_address}:8787",
                f"{_get_last_heartbeat_since_now(instance)}",
            ]
        table.add_row(
            instance.id,
            instance.public_ip_address,
            instance.private_ip_address,
            _get_instance_name(instance),
            f"{instance.launch_time}",
            typer.style(
                instance.state["Name"],
                fg=typer.colors.GREEN
                if instance.state["Name"] == "running"
                else typer.colors.YELLOW,
            ),
            *specific,
        )
    print(table)


@app.command()
def summary(env_file: Path) -> None:
    # connect to ec2
    env_key_values = dotenv_values(env_file)
    assert env_key_values
    ec2_resource = boto3.resource(
        "ec2",
        region_name=env_key_values["AUTOSCALING_EC2_REGION_NAME"],
        aws_access_key_id=env_key_values["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=env_key_values["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )

    # get all the running instances
    assert env_key_values["EC2_INSTANCES_KEY_NAME"]
    instances = ec2_resource.instances.filter(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
            {"Name": "key-name", "Values": [env_key_values["EC2_INSTANCES_KEY_NAME"]]},
        ]
    )

    # TODO: once we have the EC2 custom tags, we shall use these instead

    # print the dynamic ones
    assert env_key_values["EC2_INSTANCES_NAME_PREFIX"]
    _print_instances_details(
        instances,
        with_name=env_key_values["EC2_INSTANCES_NAME_PREFIX"],
        title="dynamic autoscaled nodes",
        computational_row=False,
    )

    # print the computational ones
    _print_instances_details(
        instances,
        with_name="osparc-computational",
        title="computational clusters",
        computational_row=True,
    )


if __name__ == "__main__":
    app()
