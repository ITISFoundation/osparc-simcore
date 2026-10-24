#!/usr/bin/env python3
"""Dev slots: lets several checkouts of this repo use one docker daemon.

Each checkout leases a slot N in [0, SLOT_COUNT). The slot sets:

- stack names: ``master-simcore``, ``ops``, ``vendors`` in slot 0;
  ``simcore-sN``, ``ops-sN``, ``vendors-sN`` otherwise
- host ports: slot-0 port + N * PORT_STRIDE
- local image tags: ``-sN`` suffix (none in slot 0)

A slot is held by a config-only docker network ``osparc-dev-slot-N`` labelled
with the checkout path. Network names are unique, so creating one is an atomic
lease. Each lease removes the markers of checkouts that no longer exist.

Stdlib only, because the root Makefile runs it with the host python3 before
any virtualenv exists.

Usage:
    dev_slot.py lease --checkout DIR [--slot N] [--env-file PATH]
    dev_slot.py env [--slot N | --env-file PATH] [--format dotenv|make]
    dev_slot.py list
    dev_slot.py shift-ports --env-file PATH < launch.template.json
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

SLOT_COUNT: Final[int] = 10
PORT_STRIDE: Final[int] = 100
SLOT_ENV_VAR: Final[str] = "OSPARC_DEV_SLOT"

MARKER_PREFIX: Final[str] = "osparc-dev-slot-"
MARKER_LABEL: Final[str] = "io.simcore.dev-slot.checkout"

# Slot-0 host ports. The compose files read them as ${NAME:-<port>}.
LEGACY_HOST_PORTS: Final[dict[str, int]] = {
    # core stack
    "API_SERVER_HOST_PORT": 8006,
    "AUTOSCALING_HOST_PORT": 8007,
    "CATALOG_HOST_PORT": 8005,
    "CLUSTERS_KEEPER_HOST_PORT": 8010,
    "DASK_SCHEDULER_DASHBOARD_HOST_PORT": 8787,
    "DASK_SCHEDULER_HOST_PORT": 8786,
    "DOCKER_API_PROXY_HOST_PORT": 8014,
    "DYNAMIC_SCHEDULER_HOST_PORT": 8012,
    "INVITATIONS_HOST_PORT": 8008,
    "NOTIFICATIONS_HOST_PORT": 8015,
    "NOTIFICATIONS_WORKER_HOST_PORT": 8016,
    "PAYMENTS_HOST_PORT": 8011,
    "POSTGRES_HOST_PORT": 5432,
    "RABBIT_MANAGEMENT_HOST_PORT": 15672,
    "RESOURCE_USAGE_TRACKER_HOST_PORT": 8009,
    "TRAEFIK_API_HOST_PORT": 10081,
    "TRAEFIK_DASHBOARD_HOST_PORT": 8080,
    "TRAEFIK_HTTP_HOST_PORT": 9081,
    # core stack, remote debugging
    "API_SERVER_DEBUG_HOST_PORT": 3006,
    "API_WORKER_DEBUG_HOST_PORT": 3025,
    "AUTOSCALING_DEBUG_HOST_PORT": 3012,
    "CATALOG_DEBUG_HOST_PORT": 3005,
    "CLUSTERS_KEEPER_DEBUG_HOST_PORT": 3015,
    "DATCORE_ADAPTER_DEBUG_HOST_PORT": 3010,
    "DIRECTOR_DEBUG_HOST_PORT": 3004,
    "DIRECTOR_V2_DEBUG_HOST_PORT": 3009,
    "DYNAMIC_SCHEDULER_DEBUG_HOST_PORT": 3016,
    "INVITATIONS_DEBUG_HOST_PORT": 3017,
    "NOTIFICATIONS_DEBUG_HOST_PORT": 3023,
    "NOTIFICATIONS_WORKER_DEBUG_HOST_PORT": 3026,
    "PAYMENTS_DEBUG_HOST_PORT": 3018,
    "RESOURCE_USAGE_TRACKER_DEBUG_HOST_PORT": 3014,
    "STORAGE_DEBUG_HOST_PORT": 3003,
    "STO_WORKER_CPU_BOUND_DEBUG_HOST_PORT": 3022,
    "STO_WORKER_DEBUG_HOST_PORT": 3021,
    "WB_API_SERVER_DEBUG_HOST_PORT": 3019,
    "WB_AUTH_DEBUG_HOST_PORT": 3024,
    "WB_DB_EVENT_LISTENER_DEBUG_HOST_PORT": 3013,
    "WB_GARBAGE_COLLECTOR_DEBUG_HOST_PORT": 3011,
    "WEBSERVER_DEBUG_HOST_PORT": 3001,
    # ops stack
    "ADMINER_HOST_PORT": 18080,
    "FLOWER_HOST_PORT": 5555,
    "JAEGER_OTLP_GRPC_HOST_PORT": 43017,
    "JAEGER_OTLP_HTTP_HOST_PORT": 43018,
    "JAEGER_UI_HOST_PORT": 16686,
    "MAILPIT_SMTP_HOST_PORT": 1025,
    "MAILPIT_UI_HOST_PORT": 8025,
    "OPENTELEMETRY_COLLECTOR_HOST_PORT": 4318,
    "PORTAINER_HOST_PORT": 9000,
    "REDIS_COMMANDER_HOST_PORT": 18081,
    "S3_CONSOLE_HOST_PORT": 9090,
    "S3_HOST_PORT": 9001,
    # frontend `qx serve`
    "QX_SERVE_HOST_PORT": 8080,
}

_SLOT_LINE: Final[re.Pattern[str]] = re.compile(rf"^{SLOT_ENV_VAR}=(?P<slot>\S*)\s*$", re.MULTILINE)
_ALREADY_EXISTS: Final[re.Pattern[str]] = re.compile(r"already exists", re.IGNORECASE)
_PORT_KEY: Final[re.Pattern[str]] = re.compile(r'(?P<key>"port"\s*:\s*)(?P<port>\d+)')


class DevSlotError(RuntimeError):
    pass


class NoFreeSlotError(DevSlotError):
    pass


class SlotTakenError(DevSlotError):
    pass


def _validate_slot(slot: int) -> int:
    if not 0 <= slot < SLOT_COUNT:
        msg = f"slot {slot} outside [0, {SLOT_COUNT})"
        raise DevSlotError(msg)
    return slot


def _suffix(slot: int) -> str:
    return f"-s{slot}" if slot else ""


def host_ports(slot: int) -> dict[str, int]:
    _validate_slot(slot)
    return {name: port + slot * PORT_STRIDE for name, port in LEGACY_HOST_PORTS.items()}


def stack_names(slot: int) -> dict[str, str]:
    """SWARM_* stack names of the slot"""
    _validate_slot(slot)
    if slot == 0:
        return {
            "SWARM_STACK_NAME": "master-simcore",
            "SWARM_OPS_STACK_NAME": "ops",
            "SWARM_VENDORS_STACK_NAME": "vendors",
        }
    return {
        "SWARM_STACK_NAME": f"simcore-s{slot}",
        "SWARM_OPS_STACK_NAME": f"ops-s{slot}",
        "SWARM_VENDORS_STACK_NAME": f"vendors-s{slot}",
    }


def pytest_stack_names(slot: int) -> tuple[str, str]:
    """(core, ops) stack names used by the integration tests"""
    _validate_slot(slot)
    return f"pytest-s{slot}-core", f"pytest-s{slot}-ops"


def derive_env(slot: int) -> dict[str, str]:
    """All variables defined by the slot"""
    env = {SLOT_ENV_VAR: f"{_validate_slot(slot)}"}
    env |= stack_names(slot)
    env["TRAEFIK_SIMCORE_ZONE"] = f"internal_simcore_stack{_suffix(slot).replace('-', '_')}"
    env["OSPARC_DEV_SLOT_SUFFIX"] = _suffix(slot)
    env["LOCAL_IMAGE_TAG_SUFFIX"] = _suffix(slot)
    env |= {name: f"{port}" for name, port in host_ports(slot).items()}
    return env


def shift_ports(text: str, slot: int) -> str:
    """Replaces each `"port": <slot-0 host port>` in a JSON text with the slot's port"""
    _validate_slot(slot)
    legacy = set(LEGACY_HOST_PORTS.values())

    def _shift(match: re.Match[str]) -> str:
        port = int(match["port"])
        return f"{match['key']}{port + slot * PORT_STRIDE if port in legacy else port}"

    return _PORT_KEY.sub(_shift, text)


def read_cached_slot(env_file: Path) -> int | None:
    """OSPARC_DEV_SLOT from an env file, or None"""
    if not env_file.exists():
        return None
    matches = _SLOT_LINE.findall(env_file.read_text())
    if not matches or not matches[-1].isdigit():
        return None
    slot = int(matches[-1])
    return slot if 0 <= slot < SLOT_COUNT else None


def write_cached_slot(env_file: Path, slot: int) -> None:
    line = f"{SLOT_ENV_VAR}={slot}"
    content = env_file.read_text() if env_file.exists() else ""
    new_content = _SLOT_LINE.sub(line, content) if _SLOT_LINE.search(content) else f"{line}\n{content}"
    if new_content != content:
        env_file.write_text(new_content)


# slot markers ----------------------------------------------------------------------------

type RunDocker = Callable[[list[str]], subprocess.CompletedProcess[str]]


def run_docker(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607


def _marker_name(slot: int) -> str:
    return f"{MARKER_PREFIX}{slot}"


def _checkout_key(checkout: Path) -> str:
    return f"{checkout.resolve()}"


def list_markers(run: RunDocker = run_docker) -> dict[int, str]:
    """{slot: checkout path} of all leased slots"""
    result = run(
        [
            "network",
            "ls",
            "--filter",
            f"label={MARKER_LABEL}",
            "--format",
            f'{{{{.Name}}}}\t{{{{.Label "{MARKER_LABEL}"}}}}',
        ]
    )
    if result.returncode != 0:
        msg = f"cannot list slot markers: {result.stderr.strip()}"
        raise DevSlotError(msg)
    markers: dict[int, str] = {}
    for line in result.stdout.splitlines():
        name, _, checkout = line.partition("\t")
        suffix = name.removeprefix(MARKER_PREFIX)
        if name.startswith(MARKER_PREFIX) and suffix.isdigit():
            markers[int(suffix)] = checkout
    return markers


def _create_marker(slot: int, checkout_key: str, run: RunDocker) -> bool:
    """False if the slot is already taken"""
    result = run(
        ["network", "create", "--config-only", "--label", f"{MARKER_LABEL}={checkout_key}", _marker_name(slot)]
    )
    if result.returncode == 0:
        return True
    if _ALREADY_EXISTS.search(result.stderr):
        return False
    msg = f"cannot create slot marker {_marker_name(slot)}: {result.stderr.strip()}"
    raise DevSlotError(msg)


def _remove_marker(slot: int, run: RunDocker) -> None:
    run(["network", "rm", _marker_name(slot)])


def _gc_stale_markers(markers: dict[int, str], run: RunDocker) -> dict[int, str]:
    alive = {}
    for slot, checkout in markers.items():
        if checkout and Path(checkout).is_dir():
            alive[slot] = checkout
        else:
            _remove_marker(slot, run)
    return alive


def _lease_requested(requested: int, key: str, markers: dict[int, str], run: RunDocker) -> int:
    _validate_slot(requested)
    if markers.get(requested) == key:
        return requested
    if requested in markers or not _create_marker(requested, key, run):
        msg = f"slot {requested} is held by checkout '{markers.get(requested, '?')}'"
        raise SlotTakenError(msg)
    return requested


def lease(
    checkout: Path,
    *,
    requested: int | None = None,
    preferred: int | None = None,
    run: RunDocker = run_docker,
) -> int:
    """Returns the checkout's slot, leasing one if it has none

    A checkout keeps its slot across calls. ``requested`` moves it to that slot.
    Otherwise ``preferred`` is tried first, then the lowest free slot.

    Raises:
        SlotTakenError: ``requested`` is held by another checkout
        NoFreeSlotError: all slots are held by other checkouts
    """
    key = _checkout_key(checkout)
    markers = _gc_stale_markers(list_markers(run), run)
    owned = sorted(slot for slot, owner in markers.items() if owner == key)

    def _keep_only(slot: int) -> int:
        for extra in owned:
            if extra != slot:
                _remove_marker(extra, run)
        return slot

    if requested is not None:
        return _keep_only(_lease_requested(requested, key, markers, run))

    if owned:
        return _keep_only(owned[0])

    candidates = ([preferred] if preferred is not None else []) + list(range(SLOT_COUNT))
    for slot in dict.fromkeys(candidates):
        if slot in markers:
            continue
        if _create_marker(slot, key, run):
            return slot
        # a concurrent lease of the same checkout may have created it
        if list_markers(run).get(slot) == key:
            return slot

    msg = f"all {SLOT_COUNT} slots are held: {markers}. Remove unused worktrees to free one"
    raise NoFreeSlotError(msg)


# CLI -----------------------------------------------------------------------------------


def _format_env(env: Mapping[str, str], fmt: str) -> str:
    if fmt == "make":
        # `?=` so that command-line and environment values win
        return "\n".join(f"{name}?={value}" for name, value in env.items())
    return "\n".join(f"{name}={value}" for name, value in env.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    lease_cmd = commands.add_parser("lease", help="print this checkout's slot, leasing one if needed")
    lease_cmd.add_argument("--checkout", type=Path, default=Path.cwd())
    lease_cmd.add_argument("--slot", type=int, default=None, help="move this checkout to this slot")
    lease_cmd.add_argument("--env-file", type=Path, default=None, help="write the slot to this file as OSPARC_DEV_SLOT")

    env_cmd = commands.add_parser("env", help="print the slot's variables")
    source = env_cmd.add_mutually_exclusive_group()
    source.add_argument("--slot", type=int, default=None)
    source.add_argument("--env-file", type=Path, default=None, help="read OSPARC_DEV_SLOT from this file")
    env_cmd.add_argument("--format", choices=("dotenv", "make"), default="dotenv")

    commands.add_parser("list", help="print the leased slots")

    shift_cmd = commands.add_parser("shift-ports", help='shift `"port": N` values from stdin to the slot\'s ports')
    shift_cmd.add_argument("--env-file", type=Path, required=True, help="read OSPARC_DEV_SLOT from this file")

    args = parser.parse_args(argv)
    try:
        if args.command == "lease":
            preferred = read_cached_slot(args.env_file) if args.env_file else None
            slot = lease(args.checkout, requested=args.slot, preferred=preferred)
            if args.env_file:
                write_cached_slot(args.env_file, slot)
            print(slot)  # noqa: T201 - CLI output consumed by make
        elif args.command == "env":
            slot = args.slot if args.slot is not None else 0
            if args.env_file:
                slot = read_cached_slot(args.env_file) or 0
            print(_format_env(derive_env(slot), args.format))  # noqa: T201 - CLI output consumed by make
        elif args.command == "shift-ports":
            sys.stdout.write(shift_ports(sys.stdin.read(), read_cached_slot(args.env_file) or 0))
        else:
            for slot, checkout in sorted(list_markers().items()):
                print(f"{slot}\t{checkout}")  # noqa: T201 - CLI output
    except DevSlotError as err:
        print(f"ERROR: {err}", file=sys.stderr)  # noqa: T201 - CLI error output
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
