"""The per-checkout dev slot (scripts/dev_slot.py) as seen by the integration test fixtures.

Several checkouts of this repo (e.g. git worktrees) share one docker daemon through numbered
dev slots: stack names, host-published ports and local image tags are derived from the slot
the checkout leases. The slot logic lives in a stdlib-only script at the repo root because the
root Makefile runs it before any virtualenv exists; this module loads that very file, so make
and pytest share one implementation.

The integration tests deploy under the checkout's slot (stacks ``pytest-s<N>-{core,ops}``,
the slot's host ports), so they cannot run while the dev stack of the *same* checkout is up
(``make down`` first); they run side by side with any other checkout.
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
    """The slot cached in .env (images built for it) is no longer the one this checkout holds"""


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
    """Leases (or re-uses) the dev slot of this checkout

    The slot cached in the repo-root .env by `make .env` is preferred. When the lease returns
    another one, images built by make (tagged for the cached slot) would not match: this fails
    unless ``accept_moved_slot`` (e.g. in CI, where no slot was cached beforehand).

    Raises:
        DevSlotMismatchError: the cached slot is held by another checkout
    """
    dev_slot = load_dev_slot_module(repo_dir)
    cached = dev_slot.read_cached_slot(repo_dir / ".env")
    slot: int = dev_slot.lease(repo_dir, preferred=cached, run=run_docker or dev_slot.run_docker)
    if cached is not None and slot != cached and not accept_moved_slot:
        msg = (
            f"this checkout's dev slot {cached} (cached in .env) is now held by another checkout and "
            f"the tests would run in slot {slot}: delete .env and run `make .env` to re-lease, then rebuild"
        )
        raise DevSlotMismatchError(msg)
    return slot


def find_foreign_port_publishers(
    docker_client: docker.client.DockerClient, ports: Iterable[int], own_stack_names: Iterable[str]
) -> dict[int, str]:
    """Maps each of ``ports`` already published on the host by anything else than the
    ``own_stack_names`` stacks (e.g. this checkout's dev stack) to the publishing service or container
    """
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
