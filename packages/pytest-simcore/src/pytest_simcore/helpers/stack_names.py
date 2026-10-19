"""Checkout-scoped names for the docker stacks the integration tests deploy.

Stack and service names are global inside a docker daemon, so two pytest sessions
running from different checkouts of this repo on one machine (e.g. two git worktrees)
must not deploy under the same names. Every checkout therefore deploys its own core
stack ``pytest-<branch>-core-<uid>`` plus a companion ops stack ``pytest-<branch>-ops-<uid>``:

- the *branch* fragment makes the stacks recognizable
  (``docker stack ls | grep '^pytest-'``), truncated in the middle when needed so head
  and tail of the branch name survive
- the *uid* fragment (hash of the checkout directory) tells checkouts apart — including
  two worktrees on the same branch — and stays *stable across runs* of one checkout, so
  a stack kept up with ``--keep-docker-up`` is re-deployed onto instead of piled up next
  to a new one. It is also identical across the xdist workers of a run.

Both names stay within ``MAX_STACK_NAME_LEN`` so that the names ``docker stack deploy``
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

_STACK_PREFIX: Final[str] = "pytest"  # spells it out so test stacks are unmistakable
_UID_LEN: Final[int] = 4
# role fragments, placed before the uid so core and ops names keep the same prefix
# and the uid stays aligned at the end of both names
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
    """Best-effort human-readable git reference of the checkout the tests run from

    NOTE: in worktrees each checkout has its own HEAD, so this correctly reports the
    branch of the worktree the tests are running from. On a detached HEAD (CI checkouts,
    rebases) the short SHA is used, and if git is unavailable at all a fixed token
    identifies the source instead (uniqueness never relies on this part).
    """
    if "CI" in os.environ:
        # GITHUB_HEAD_REF is set on pull_request events, GITHUB_REF_NAME on push events
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


def _create_uid(token: str) -> str:
    return hashlib.sha1(token.encode(), usedforsecurity=False).hexdigest()[:_UID_LEN]


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
    return _create_uid(get_checkout_token(repo_dir))


def is_service_in_stack(service_name: str, stack_name: str) -> bool:
    """True when ``service_name`` is a service deployed by the ``stack_name`` stack

    "docker stack deploy" names every deployed object ``{stack}_{name}`` and object names
    are global inside the daemon, so any filter distinguishing this checkout's objects
    from a co-tenant checkout's must match on exactly this prefix.
    """
    return service_name.startswith(f"{stack_name}_")


def _create_readable_branch(git_ref: str, role_len: int) -> str:
    # sized against the LONGEST role so core and ops truncate identically and therefore
    # share one prefix, with the uid landing at the same offset in both names
    budget = MAX_STACK_NAME_LEN - len(_STACK_PREFIX) - _UID_LEN - len("-") * 3 - role_len
    readable = _NON_NAME_CHARS.sub("-", git_ref.lower()).strip("-")
    if len(readable) > budget:
        # cut out of the MIDDLE (not the tail) so both ends of the branch stay
        # recognizable; hyphens landing on the cut are dropped so the name never carries
        # consecutive or dangling ones
        head_len = -(-budget // 2)  # ceil
        tail = readable[len(readable) - (budget - head_len) :] if budget > head_len else ""
        readable = readable[:head_len].rstrip("-") + tail.lstrip("-")
    return readable


def _create_stack_name(readable_branch: str, uid: str, role: str) -> str:
    stack_name = "-".join(part for part in (_STACK_PREFIX, readable_branch, role, uid) if part)
    assert len(stack_name) <= MAX_STACK_NAME_LEN
    return stack_name


def compute_stack_names(git_ref: str, checkout_token: str) -> tuple[str, str]:
    """Returns the (core, ops) stack names of one checkout

    Both names start with 'pytest-' so test-owned stacks remain easy to spot (and to
    garbage-collect) on a shared daemon.
    """
    uid = _create_uid(checkout_token)
    longest_role_len = max(len(_CORE_STACK_ROLE), len(_OPS_STACK_ROLE))
    readable_branch = _create_readable_branch(git_ref, longest_role_len)
    core_stack_name = _create_stack_name(readable_branch, uid, role=_CORE_STACK_ROLE)
    ops_stack_name = _create_stack_name(readable_branch, uid, role=_OPS_STACK_ROLE)
    return core_stack_name, ops_stack_name
