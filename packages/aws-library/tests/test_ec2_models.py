# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aws_library.ec2.models import AWSTagKey, AWSTagValue, Resources
from pydantic import ByteSize, ValidationError, parse_obj_as


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
            Resources(cpus=0.1, ram=ByteSize(-1)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources(cpus=1.1, ram=ByteSize(33)),
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
            Resources(cpus=0, ram=ByteSize(0)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources.construct(cpus=-1, ram=ByteSize(-34)),
        ),
        (
            Resources(cpus=0.1, ram=ByteSize(-1)),
            Resources(cpus=1, ram=ByteSize(34)),
            Resources.construct(cpus=-0.9, ram=ByteSize(-35)),
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
        parse_obj_as(AWSTagKey, ec2_tag_key)

    # for a value it does not
    parse_obj_as(AWSTagValue, ec2_tag_key)
