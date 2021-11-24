# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

import pytest
from packaging.version import Version
from service_integration.versioning import (
    ExecutableVersionInfo,
    ServiceVersionInfo,
    bump_version_string,
)

# TESTS ------------------------------------------


def test_pep404_compare_versions():
    # TODO: replace pkg_resources with https://importlib-metadata.readthedocs.io/en/latest/index.html so it is standard in 3.8

    # A reminder from https://setuptools.readthedocs.io/en/latest/userguide/distribution.html#specifying-your-project-s-version
    assert Version("1.9.a.dev") == Version("1.9a0dev")
    assert Version("2.1-rc2") < Version("2.1")
    assert Version("0.6a9dev") < Version("0.6a9")

    # same release but one is pre-release
    assert (
        Version("2.1-rc2").release == Version("2.1").release
        and Version("2.1-rc2").is_prerelease
    )


BUMP_PARAMS = [
    # "upgrade,current_version,new_version",
    ("patch", "1.1.1", "1.1.2"),
    ("minor", "1.1.1", "1.2.0"),
    ("major", "1.1.1", "2.0.0"),
]


@pytest.mark.parametrize(
    "bump,current_version,new_version",
    BUMP_PARAMS,
)
def test_bump_version_string(
    bump: str,
    current_version: str,
    new_version: str,
):
    assert bump_version_string(current_version, bump) == new_version


@pytest.mark.parametrize(
    "model_cls",
    (ExecutableVersionInfo, ServiceVersionInfo),
)
def test_version_info_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", json.dumps(example, indent=1))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
