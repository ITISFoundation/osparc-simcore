import pytest
from aws_library.ec2._errors import EC2TooManyInstancesError
from aws_library.ec2._models import EC2InstanceType
from fastapi import FastAPI
from pydantic import TypeAdapter
from simcore_service_autoscaling.utils.capacity_distribution import cap_needed_instances
from simcore_service_autoscaling.utils.models import InstanceToLaunch


def _instance_type(name: str) -> EC2InstanceType:
    return TypeAdapter(EC2InstanceType).validate_python(name)


def _build_needed_instances(names_and_counts: list[tuple[str, int]]):
    """Helper to create an ordered mapping of InstanceToLaunch -> count."""
    return {
        InstanceToLaunch(instance_type=_instance_type(name), node_labels={}): count
        for name, count in names_and_counts
    }


def _patch_ec2_client(monkeypatch: pytest.MonkeyPatch, current_count: int):
    class _FakeEC2:
        async def get_instances(self, **_: object):
            return [object() for _ in range(current_count)]

    monkeypatch.setattr(
        "simcore_service_autoscaling.utils.capacity_distribution.get_ec2_client",
        lambda _app: _FakeEC2(),
    )


def _patch_app_settings(monkeypatch: pytest.MonkeyPatch, app_settings):
    monkeypatch.setattr(
        "simcore_service_autoscaling.utils.capacity_distribution.get_application_settings",
        lambda _app: app_settings,
    )


@pytest.mark.asyncio
async def test_cap_needed_instances_no_capping(
    initialized_app: FastAPI,
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    _patch_app_settings(monkeypatch, app_settings)
    _patch_ec2_client(monkeypatch, current_count=1)

    # Ensure the requested total fits in the max boundary
    needed_instances = _build_needed_instances([("t2.micro", 1), ("t3.medium", 1)])

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert result == needed_instances
    assert sum(result.values()) == 2
    assert 1 + 2 <= max_instances


@pytest.mark.asyncio
async def test_cap_needed_instances_minimal_cap(
    initialized_app: FastAPI,
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    if max_instances < 3:
        pytest.skip("Not enough max instances configured to test minimal capping")

    # Force creatable < number of types (3 types, creatable 2)
    current = max_instances - 2
    _patch_app_settings(monkeypatch, app_settings)
    _patch_ec2_client(monkeypatch, current_count=current)

    needed_instances = _build_needed_instances(
        [("t2.micro", 3), ("t3.medium", 2), ("m5.large", 1)]
    )

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == 2
    # Minimal cap keeps first batches, one each
    keys = list(result.keys())
    assert keys[0].instance_type == _instance_type("t2.micro")
    assert keys[1].instance_type == _instance_type("t3.medium")
    assert list(result.values()) == [1, 1]


@pytest.mark.asyncio
async def test_cap_needed_instances_proportional_cap(
    initialized_app: FastAPI,
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    desired_creatable = 4
    if max_instances < desired_creatable:
        pytest.skip("Not enough max instances configured to test proportional capping")

    _patch_app_settings(monkeypatch, app_settings)
    # Force creatable to desired_creatable
    _patch_ec2_client(monkeypatch, current_count=max_instances - desired_creatable)

    needed_instances = _build_needed_instances([("t2.micro", 3), ("t3.medium", 3)])

    result = await cap_needed_instances(
        initialized_app,
        needed_instances,
        ec2_tags={},
    )

    assert sum(result.values()) == desired_creatable

    # Per-type sums do not exceed requested
    per_type: dict[EC2InstanceType, int] = {}
    for batch, count in result.items():
        per_type[batch.instance_type] = per_type.get(batch.instance_type, 0) + count

    requested = {
        _instance_type("t2.micro"): 3,
        _instance_type("t3.medium"): 3,
    }
    assert all(
        per_type.get(t, 0) <= requested_val for t, requested_val in requested.items()
    )


@pytest.mark.asyncio
async def test_cap_needed_instances_already_at_max_raises(
    initialized_app: FastAPI,
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    max_instances = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    _patch_app_settings(monkeypatch, app_settings)
    # Already at max -> raises
    _patch_ec2_client(monkeypatch, current_count=max_instances)

    needed_instances = _build_needed_instances([("t2.micro", 1)])

    with pytest.raises(EC2TooManyInstancesError):
        await cap_needed_instances(
            initialized_app,
            needed_instances,
            ec2_tags={},
        )
