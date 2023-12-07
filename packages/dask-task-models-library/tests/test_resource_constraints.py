from dask_task_models_library.constants import DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY
from dask_task_models_library.resource_constraints import (
    create_ec2_resource_constraint_key,
    get_ec2_instance_type_from_resources,
)
from faker import Faker


def test_create_ec2_resource_constraint_key(faker: Faker):
    faker_instance_type = faker.pystr()
    assert (
        create_ec2_resource_constraint_key(faker_instance_type)
        == f"{DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY}:{faker_instance_type}"
    )

    empty_instance_type = ""
    assert (
        create_ec2_resource_constraint_key(empty_instance_type)
        == f"{DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY}:"
    )


def test_get_ec2_instance_type_from_resources(faker: Faker):
    empty_task_resources = {}
    assert get_ec2_instance_type_from_resources(empty_task_resources) is None
    no_ec2_types_in_resources = {"blahblah": 1}
    assert get_ec2_instance_type_from_resources(no_ec2_types_in_resources) is None

    faker_instance_type = faker.pystr()
    ec2_type_in_resources = {create_ec2_resource_constraint_key(faker_instance_type): 1}
    assert (
        get_ec2_instance_type_from_resources(ec2_type_in_resources)
        == faker_instance_type
    )
