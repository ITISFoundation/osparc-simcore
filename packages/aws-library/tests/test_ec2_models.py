# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aws_library.ec2._models import AWSTagKey, AWSTagValue, EC2InstanceData, Resources
from faker import Faker
from pydantic import ByteSize, TypeAdapter, ValidationError


@pytest.mark.parametrize(
    "a,b,a_greater_or_equal_than_b",
    [
        (
            Resources(cpus=0.2, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.05, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,
        ),
    ],
)
def test_resources_ge_operator(
    a: Resources, b: Resources, a_greater_or_equal_than_b: bool
):
    assert (a >= b) is a_greater_or_equal_than_b


@pytest.mark.parametrize(
    "a,b,a_greater_than_b",
    [
        (
            Resources(cpus=0.2, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.05, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(0)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,
        ),
    ],
)
def test_resources_gt_operator(a: Resources, b: Resources, a_greater_than_b: bool):
    assert (a > b) is a_greater_than_b


@pytest.mark.parametrize(
    "a,b,result",
    [
        (
            Resources(cpus=0, ram=ByteSize(0)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1, ram=ByteSize(34)),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1.1, ram=ByteSize(35)),
        ),
    ],
)
def test_resources_add(a: Resources, b: Resources, result: Resources):
    assert a + b == result
    a += b
    assert a == result


def test_resources_create_as_empty():
    assert Resources.create_as_empty() == Resources(cpus=0, ram=ByteSize(0))


@pytest.mark.parametrize(
    "a,b,result",
    [
        (
            Resources(cpus=0, ram=ByteSize(34)),
            Resources(cpus=1, ram=ByteSize(0)),
            Resources.model_construct(cpus=-1, ram=ByteSize(34)),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(34)),
            Resources(cpus=1, ram=ByteSize(1)),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(33)),
        ),
    ],
)
def test_resources_sub(a: Resources, b: Resources, result: Resources):
    assert a - b == result
    a -= b
    assert a == result


@pytest.mark.parametrize("ec2_tag_key", ["", "/", " ", ".", "..", "_index"])
def test_aws_tag_key_invalid(ec2_tag_key: str):
    # for a key it raises
    with pytest.raises(ValidationError):
        TypeAdapter(AWSTagKey).validate_python(ec2_tag_key)

    # for a value it does not
    TypeAdapter(AWSTagValue).validate_python(ec2_tag_key)


def test_ec2_instance_data_hashable(faker: Faker):
    first_set_of_ec2s = {
        EC2InstanceData(
            faker.date_time(),
            faker.pystr(),
            faker.pystr(),
            f"{faker.ipv4()}",
            "g4dn.xlarge",
            "running",
            Resources(
                cpus=faker.pyfloat(min_value=0.1),
                ram=ByteSize(faker.pyint(min_value=123)),
            ),
            {AWSTagKey("mytagkey"): AWSTagValue("mytagvalue")},
        )
    }
    second_set_of_ec2s = {
        EC2InstanceData(
            faker.date_time(),
            faker.pystr(),
            faker.pystr(),
            f"{faker.ipv4()}",
            "g4dn.xlarge",
            "running",
            Resources(
                cpus=faker.pyfloat(min_value=0.1),
                ram=ByteSize(faker.pyint(min_value=123)),
            ),
            {AWSTagKey("mytagkey"): AWSTagValue("mytagvalue")},
        )
    }

    union_of_sets = first_set_of_ec2s.union(second_set_of_ec2s)
    assert next(iter(first_set_of_ec2s)) in union_of_sets
    assert next(iter(second_set_of_ec2s)) in union_of_sets
