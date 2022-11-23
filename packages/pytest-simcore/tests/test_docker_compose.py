# pylint: disable=redefined-outer-name

from textwrap import dedent

import pytest
from pytest import FixtureRequest
from pytest_simcore.docker_compose import _escape_cpus


@pytest.fixture(params=[0.1, 1, 1.0, 100.2313131231])
def number_of_cpus(request: FixtureRequest) -> float:
    return request.param


@pytest.fixture
def yaml_sample(number_of_cpus: int) -> str:
    return dedent(
        f"""
services:
  a-service:
    deploy:
      resources:
        limits:
          cpus: {number_of_cpus}
        """
    )


def test_sequence(yaml_sample: str, number_of_cpus: int):
    escaped_yaml = _escape_cpus(yaml_sample)
    assert f"cpus: {number_of_cpus}" not in escaped_yaml
    assert f"cpus: '{number_of_cpus}'" in escaped_yaml
