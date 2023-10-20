""" Free helper functions for AWS API

"""

import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from textwrap import dedent

from .._meta import VERSION
from ..core.errors import ConfigurationError, Ec2InstanceNotFoundError
from ..core.settings import ApplicationSettings
from ..models import EC2InstanceType, Resources

logger = logging.getLogger(__name__)


def get_ec2_tags_dynamic(app_settings: ApplicationSettings) -> dict[str, str]:
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return {
        "io.simcore.autoscaling.version": f"{VERSION}",
        "io.simcore.autoscaling.monitored_nodes_labels": json.dumps(
            app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
        ),
        "io.simcore.autoscaling.monitored_services_labels": json.dumps(
            app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
        ),
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        "Name": f"{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_NAME_PREFIX}-{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME}",
    }


def get_ec2_tags_computational(app_settings: ApplicationSettings) -> dict[str, str]:
    assert app_settings.AUTOSCALING_DASK  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return {
        "io.simcore.autoscaling.version": f"{VERSION}",
        "io.simcore.autoscaling.dask-scheduler_url": json.dumps(
            app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL
        ),
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        "Name": f"{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_NAME_PREFIX}-{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME}",
    }


def compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )


def closest_instance_policy(
    ec2_instance: EC2InstanceType,
    resources: Resources,
) -> float:
    if ec2_instance.cpus < resources.cpus or ec2_instance.ram < resources.ram:
        return 0
    # compute a score for all the instances that are above expectations
    # best is the exact ec2 instance
    cpu_ratio = float(ec2_instance.cpus - resources.cpus) / float(ec2_instance.cpus)
    ram_ratio = float(ec2_instance.ram - resources.ram) / float(ec2_instance.ram)
    return 100 * (1.0 - cpu_ratio) * (1.0 - ram_ratio)


def find_best_fitting_ec2_instance(
    allowed_ec2_instances: list[EC2InstanceType],
    resources: Resources,
    score_type: Callable[[EC2InstanceType, Resources], float] = closest_instance_policy,
) -> EC2InstanceType:
    if not allowed_ec2_instances:
        raise ConfigurationError(msg="allowed ec2 instances is missing!")
    score_to_ec2_candidate: dict[float, EC2InstanceType] = OrderedDict(
        sorted(
            {
                score_type(instance, resources): instance
                for instance in allowed_ec2_instances
            }.items(),
            reverse=True,
        )
    )

    score, instance = next(iter(score_to_ec2_candidate.items()))
    if score == 0:
        raise Ec2InstanceNotFoundError(
            needed_resources=resources, msg="no adequate EC2 instance found!"
        )
    return instance
