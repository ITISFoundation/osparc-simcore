import pytest
from fastapi import FastAPI
from simcore_service_autoscaling.constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
)
from simcore_service_autoscaling.modules import BaseAutoscaling
from simcore_service_autoscaling.modules.auto_scaling_mode_computational import (
    ComputationalAutoscaling,
)
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.utils.buffer_machines_pool_core import (
    get_activated_buffer_ec2_tags,
    get_deactivated_buffer_ec2_tags,
)


@pytest.mark.parametrize(
    "auto_scaling_mode", [(DynamicAutoscaling()), (ComputationalAutoscaling())]
)
def test_get_activated_buffer_ec2_tags(
    initialized_app: FastAPI, auto_scaling_mode: BaseAutoscaling
):
    activated_buffer_tags = get_activated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
    )
    assert (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | ACTIVATED_BUFFER_MACHINE_EC2_TAGS
    ) == activated_buffer_tags


@pytest.mark.parametrize(
    "auto_scaling_mode", [(DynamicAutoscaling()), (ComputationalAutoscaling())]
)
def test_get_deactivated_buffer_ec2_tags(
    initialized_app: FastAPI, auto_scaling_mode: BaseAutoscaling
):
    deactivated_buffer_tags = get_deactivated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
    )
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    assert expected_tags == deactivated_buffer_tags


def test_is_buffer_machine():
    ...


def test_dump_pre_pulled_images_as_tags():
    ...


def test_load_pre_pulled_images_from_tags():
    ...
