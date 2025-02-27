# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import itertools
from typing import Any

import pytest
from packaging.version import Version
from pydantic import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    iter_model_examples_in_class,
)
from service_integration.versioning import (
    ExecutableVersionInfo,
    ServiceVersionInfo,
    bump_version_string,
)


def test_pep404_compare_versions():
    # A reminder from https://setuptools.readthedocs.io/en/latest/userguide/distribution.html#specifying-your-project-s-version
    assert Version("1.9.a.dev") == Version("1.9a0dev")
    assert Version("2.1-rc2") < Version("2.1")
    assert Version("0.6a9dev") < Version("0.6a9")

    # same release but one is pre-release
    assert Version("2.1-rc2").release == Version("2.1").release
    assert Version("2.1-rc2").is_prerelease


_BUMP_PARAMS = [
    # "upgrade,current_version,new_version",
    ("patch", "1.1.1", "1.1.2"),
    ("minor", "1.1.1", "1.2.0"),
    ("major", "1.1.1", "2.0.0"),
]


@pytest.mark.parametrize(
    "bump,current_version,new_version",
    _BUMP_PARAMS,
)
def test_bump_version_string(
    bump: str,
    current_version: str,
    new_version: str,
):
    assert bump_version_string(current_version, bump) == new_version


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    itertools.chain(
        iter_model_examples_in_class(ExecutableVersionInfo),
        iter_model_examples_in_class(ServiceVersionInfo),
    ),
)
def test_version_info_model_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )
