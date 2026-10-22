"""Dev slot of the checkout for the integration tests (see scripts/dev_slot.py).

Loads scripts/dev_slot.py so that make and pytest use the same code.

The tests deploy ``pytest-sN-<branch>-{core,ops}`` on the slot's host ports. They can
run next to other checkouts, but not next to this checkout's dev stack.
"""

import functools
import importlib.util
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Final

import docker
import docker.client

_DEV_SLOT_SCRIPT: Final[Path] = Path("scripts") / "dev_slot.py"


class DevSlotMismatchError(RuntimeError):
    """Another checkout holds the slot cached in .env, which the images were built for"""


@functools.cache
def load_dev_slot_module(repo_dir: Path) -> ModuleType:
    path = repo_dir / _DEV_SLOT_SCRIPT
    spec = importlib.util.spec_from_file_location("osparc_dev_slot", path)
    assert spec, f"cannot load {path}"
    assert spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lease_checkout_slot(repo_dir: Path, *, accept_moved_slot: bool, run_docker: Callable | None = None) -> int:
    """Returns the checkout's slot, leasing one if needed

    Prefers the slot cached in .env. Getting a different slot fails unless
    ``accept_moved_slot``, because the local images are tagged for the cached slot.

    Raises:
        DevSlotMismatchError: the cached slot is held by another checkout
    """
    dev_slot = load_dev_slot_module(repo_dir)
    cached = dev_slot.read_cached_slot(repo_dir / ".env")
    slot: int = dev_slot.lease(repo_dir, preferred=cached, run=run_docker or dev_slot.run_docker)
    if cached is not None and slot != cached and not accept_moved_slot:
        msg = (
            f"dev slot {cached} from .env is held by another checkout, the tests would use slot {slot}. "
            "Delete .env, run `make .env` and rebuild the images"
        )
        raise DevSlotMismatchError(msg)
    return slot


def find_foreign_port_publishers(
    docker_client: docker.client.DockerClient, ports: Iterable[int], own_stack_names: Iterable[str]
) -> dict[int, str]:
    """Returns {port: publisher} for ``ports`` published by services or containers
    outside ``own_stack_names``"""
    wanted = set(ports)
    own = set(own_stack_names)
    publishers: dict[int, str] = {}

    for service in docker_client.services.list():
        labels = service.attrs.get("Spec", {}).get("Labels", {}) or {}
        if labels.get("com.docker.stack.namespace") in own:
            continue
        for port in service.attrs.get("Endpoint", {}).get("Ports", []) or []:
            if (published := port.get("PublishedPort")) in wanted:
                publishers[published] = f"service {service.name}"

    for container in docker_client.containers.list():
        if container.labels.get("com.docker.stack.namespace") in own:
            continue
        for bindings in (container.attrs.get("NetworkSettings", {}).get("Ports") or {}).values():
            for binding in bindings or []:
                if (host_port := int(binding.get("HostPort") or 0)) in wanted:
                    publishers.setdefault(host_port, f"container {container.name}")

    return publishers
