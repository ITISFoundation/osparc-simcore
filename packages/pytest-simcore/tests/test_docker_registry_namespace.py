from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_simcore.docker_registry import _get_local_tag_suffix, _get_worker_registry_namespace, _owned_build_context


@pytest.mark.parametrize(
    "workerinput,expected_namespace",
    [
        pytest.param(None, "", id="no-xdist"),
        pytest.param({"workerid": "gw0"}, "gw0/", id="xdist-worker"),
    ],
)
def test_registry_namespace_is_per_worker_and_empty_outside_xdist(
    workerinput: dict[str, str] | None, expected_namespace: str
):
    request: Any = SimpleNamespace(config=SimpleNamespace(workerinput=workerinput))

    assert _get_worker_registry_namespace(request) == expected_namespace


@pytest.mark.parametrize(
    "workerinput,expected_suffix",
    [
        pytest.param(None, "master", id="no-xdist"),
        pytest.param({"workerid": "gw0"}, "gw0", id="xdist-worker"),
    ],
)
def test_local_tag_suffix_is_per_worker(workerinput: dict[str, str] | None, expected_suffix: str):
    """the intermediate `...-owned` tag names an image of the shared daemon store, so two workers
    rebuilding the same source must not move that name onto each other's image"""
    request: Any = SimpleNamespace(config=SimpleNamespace(workerinput=workerinput))

    assert _get_local_tag_suffix(request) == expected_suffix


def test_owned_build_context_writes_the_dockerfile_outside_the_current_directory():
    # the CWD is one directory shared by every xdist worker, so nothing may be written into it
    cwd = Path.cwd().resolve()

    with _owned_build_context("busybox", "1.0.0", "gw0") as (context, tag):
        assert Path(context).resolve() != cwd
        assert (Path(context) / "Dockerfile").read_text() == "FROM busybox:1.0.0"
        assert tag == "1.0.0-owned-gw0"

    assert not Path(context).exists(), "the build context must not outlive the injection"
