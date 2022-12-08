""" Free helper functions for AWS API

"""

import logging
from collections import OrderedDict
from textwrap import dedent
from typing import Callable

from ..core.errors import ConfigurationError, Ec2InstanceNotFoundError
from ..models import EC2Instance, Resources

logger = logging.getLogger(__name__)


def compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )


def closest_instance_policy(
    ec2_instance: EC2Instance,
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
    allowed_ec2_instances: list[EC2Instance],
    resources: Resources,
    score_type: Callable[[EC2Instance, Resources], float] = closest_instance_policy,
) -> EC2Instance:
    if not allowed_ec2_instances:
        raise ConfigurationError(msg="allowed ec2 instances is missing!")
    score_to_ec2_candidate: dict[float, EC2Instance] = OrderedDict(
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
