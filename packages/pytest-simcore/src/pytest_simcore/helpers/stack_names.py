"""Names of the docker stacks the integration tests deploy.

Stack names are daemon-global, so each checkout deploys under its dev slot
(see pytest_simcore.helpers.dev_slot): ``pytest-sN-<branch>-{core,ops}``.
The slot keeps checkouts apart, the branch tells humans what a stack is.

Stack names stay within ``MAX_STACK_NAME_LEN`` so that the names ``docker stack deploy``
derives from them (``{stack}_{service}`` and ``{stack}_{network}``) each remain a valid
single DNS label.
"""

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

# "docker stack deploy" names both its services ("{stack}_{service}", also the overlay
# network alias) and its networks ("{stack}_{network}"), which must each fit in one DNS
# label (<= 63 chars); the longest name deployed by the tests is the network
# "computational_services_subnet" (29 chars, see services/docker-compose.yml)
MAX_STACK_NAME_LEN: Final[int] = 63 - len("_") - len("computational_services_subnet")

_UID_LEN: Final[int] = 4
_CORE_STACK_ROLE: Final[str] = "core"
_OPS_STACK_ROLE: Final[str] = "ops"
_FALLBACK_REF: Final[str] = "local"

# docker service/stack names must match [a-zA-Z0-9](-?[a-zA-Z0-9])*
_NON_NAME_CHARS: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


def _git(git_exe: str, *args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        [git_exe, *args], check=True, capture_output=True, text=True, cwd=f"{cwd}"
    ).stdout.strip()


def get_git_ref(repo_dir: Path) -> str:
    """Branch of the checkout, the short SHA on a detached HEAD, or "local" without git

    In CI the branch comes from GITHUB_HEAD_REF (pull requests) or GITHUB_REF_NAME (pushes).
    """
    if "CI" in os.environ:
        ref = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
        if ref:
            return ref

    git_exe = shutil.which("git")
    if git_exe is None:
        return _FALLBACK_REF

    try:
        ref = _git(git_exe, "rev-parse", "--abbrev-ref", "HEAD", cwd=repo_dir)
        if ref == "HEAD":  # detached
            ref = _git(git_exe, "rev-parse", "--short", "HEAD", cwd=repo_dir)
        return ref or _FALLBACK_REF
    except OSError, subprocess.CalledProcessError:
        return _FALLBACK_REF


def get_slot_stack_prefix(slot: int) -> str:
    """Prefix shared by all test stacks of the slot, whatever their branch"""
    return f"pytest-s{slot}-"


def _create_readable_branch(git_ref: str, budget: int) -> str:
    readable = _NON_NAME_CHARS.sub("-", git_ref.lower()).strip("-")
    if len(readable) > budget:
        # cut out of the middle so that both ends of the branch stay recognizable
        head_len = -(-budget // 2)  # ceil
        tail = readable[len(readable) - (budget - head_len) :] if budget > head_len else ""
        readable = readable[:head_len].rstrip("-") + tail.lstrip("-")
    return readable


def compute_stack_names(slot: int, git_ref: str) -> tuple[str, str]:
    """Returns the (core, ops) test stack names of a slot"""
    prefix = get_slot_stack_prefix(slot)
    longest_role_len = max(len(_CORE_STACK_ROLE), len(_OPS_STACK_ROLE))
    # sized against the longest role, so core and ops carry the same branch fragment
    budget = MAX_STACK_NAME_LEN - len(prefix) - len("-") - longest_role_len
    branch = _create_readable_branch(git_ref, budget)
    stem = f"{prefix}{branch}-" if branch else prefix
    core_stack_name, ops_stack_name = f"{stem}{_CORE_STACK_ROLE}", f"{stem}{_OPS_STACK_ROLE}"
    assert len(core_stack_name) <= MAX_STACK_NAME_LEN
    assert len(ops_stack_name) <= MAX_STACK_NAME_LEN
    return core_stack_name, ops_stack_name


def get_checkout_token(repo_dir: Path) -> str:
    """Token identifying one checkout: identical for every run and every xdist worker of
    the same checkout, different for any other checkout (e.g. another git worktree)

    NOTE: resolved to keep the token stable when the same checkout is reached through a
    symlink or a different path spelling.
    """
    return f"{repo_dir.resolve()}"


def get_checkout_uid(repo_dir: Path) -> str:
    """Short identifier of one checkout, to keep docker objects created outside of the
    stacks (plain containers) scoped to the checkout as well"""
    return hashlib.sha1(get_checkout_token(repo_dir).encode(), usedforsecurity=False).hexdigest()[:_UID_LEN]


def is_service_in_stack(service_name: str, stack_name: str) -> bool:
    """True when ``service_name`` is a service deployed by the ``stack_name`` stack

    "docker stack deploy" names every deployed object ``{stack}_{name}`` and object names
    are global inside the daemon, so any filter distinguishing this checkout's objects
    from a co-tenant checkout's must match on exactly this prefix.
    """
    return service_name.startswith(f"{stack_name}_")
