# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aws_library.ec2._models import (
    AWSTagKey,
    AWSTagValue,
    EC2InstanceBootSpecific,
    EC2InstanceData,
    Resources,
)
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
            False,  # CPU is smaller
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,  # RAM is smaller
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": "2"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,  # string resources are not comparable so "2" is NOT considered larger
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "no"}),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "no"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            False,
        ),
    ],
    ids=str,
)
def test_resources_ge_operator(a: Resources, b: Resources, a_greater_or_equal_than_b: bool):
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
            False,  # CPU is smaller
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0)),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(0), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            False,  # ram is not enough
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            True,
        ),
        (
            Resources(cpus=15, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=20, ram=ByteSize(128)),
            False,  # NOTE: CPU and RAM are not enough
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": "2"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 2}),
            False,  # string resources are not comparable, so a is not greater than b
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1)),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            False,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "no"}),
            True,
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "no"}),
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"SSE": "yes"}),
            False,
        ),
    ],
    ids=str,
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
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1.1, ram=ByteSize(35), generic_resources={"GPU": 1}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources(cpus=1.1, ram=ByteSize(35), generic_resources={"GPU": 1}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources(cpus=1.1, ram=ByteSize(35), generic_resources={"GPU": 2}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1, "SSE": "yes"}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources(cpus=1.1, ram=ByteSize(35), generic_resources={"GPU": 2}),
        ),  # string resources are not summed
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": "1"}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources(
                cpus=1.1,
                ram=ByteSize(35),
            ),
        ),  # string resources are ignored in summation
    ],
    ids=str,
)
def test_resources_add(a: Resources, b: Resources, result: Resources):
    assert a + b == result
    a += b
    assert a == result


def test_resources_create_as_empty():
    assert Resources.create_as_empty() == Resources(cpus=0, ram=ByteSize(0), generic_resources={})


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
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(-33), generic_resources={"GPU": 1}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1)),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(-33), generic_resources={"GPU": -1}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(-33), generic_resources={"GPU": 0}),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": 1, "SSE": "yes"}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(-33), generic_resources={"GPU": 0}),
        ),  # string resources are not summed
        (
            Resources(cpus=0.1, ram=ByteSize(1), generic_resources={"GPU": "1"}),
            Resources(cpus=1, ram=ByteSize(34), generic_resources={"GPU": 1}),
            Resources.model_construct(cpus=-0.9, ram=ByteSize(-33)),
        ),  # string resources are ignored in summation
        (
            Resources(cpus=14.6, ram=ByteSize(29850022707), generic_resources={}),
            Resources(cpus=14.6, ram=ByteSize(29850022707), generic_resources={}),
            Resources(cpus=0, ram=ByteSize(0), generic_resources={}),
        ),
    ],
)
def test_resources_sub(a: Resources, b: Resources, result: Resources):
    assert a - b == result
    a -= b
    assert a == result


def test_resources_flat_dict():
    r = Resources(cpus=0.1, ram=ByteSize(1024), generic_resources={"GPU": 2, "SSE": "yes"})
    flat = r.as_flat_dict()
    assert flat == {"cpus": 0.1, "ram": 1024, "GPU": 2, "SSE": "yes"}

    reconstructed = Resources.from_flat_dict(flat)
    assert reconstructed == r

    # test with mapping
    flat_with_other_names = {"CPU": 0.1, "RAM": 1024, "GPU": 2, "SSE": "yes"}
    reconstructed2 = Resources.from_flat_dict(flat_with_other_names, mapping={"CPU": "cpus", "RAM": "ram"})
    assert reconstructed2 == r


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
            {
                TypeAdapter(AWSTagKey).validate_python("mytagkey"): TypeAdapter(AWSTagValue).validate_python(
                    "mytagvalue"
                )
            },
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
            {
                TypeAdapter(AWSTagKey).validate_python("mytagkey"): TypeAdapter(AWSTagValue).validate_python(
                    "mytagvalue"
                )
            },
        )
    }

    union_of_sets = first_set_of_ec2s.union(second_set_of_ec2s)
    assert next(iter(first_set_of_ec2s)) in union_of_sets
    assert next(iter(second_set_of_ec2s)) in union_of_sets


def test_ec2_instance_boot_specific_with_invalid_custom_script(faker: Faker):
    valid_model = EC2InstanceBootSpecific.model_json_schema()["examples"][0]
    invalid_model = {**valid_model, "custom_boot_scripts": ["echo 'missing end quote"]}

    with pytest.raises(ValueError, match="Invalid bash call"):
        EC2InstanceBootSpecific(**invalid_model)
