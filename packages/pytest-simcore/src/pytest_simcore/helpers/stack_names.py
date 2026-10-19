"""Run-scoped names for the docker stacks the integration tests deploy.

Stack and service names are global inside a docker daemon, so two pytest sessions
running concurrently on the same machine (e.g. from two git worktrees of this repo)
must not deploy under the same names. Every run therefore deploys its own core stack
``pytest-<branch>-<uid>`` plus a companion ops stack ``pytest-<branch>-<uid>-ops``:

- the *branch* fragment makes the stacks recognizable per checkout
  (``docker stack ls | grep pytest-``)
- the *uid* fragment (hash of the run's shared temp dir) keeps two concurrent runs of
  the SAME branch apart, and is identical across the xdist workers of one run so they
  all agree on the stack name.

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

_STACK_PREFIX: Final[str] = "pytest"
_UID_LEN: Final[int] = 4
_OPS_STACK_SUFFIX: Final[str] = "ops"
_FALLBACK_REF: Final[str] = "local"

# pytest-xdist roots every worker's base temp dir under "{run}/popen-gwN": the parent is
# shared by the controller and every worker of one run (and only of that run)
_XDIST_WORKER_BASETEMP_PATTERN: Final[re.Pattern[str]] = re.compile(r"^popen-gw\d+$")

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


def get_run_dir(basetemp: Path) -> Path:
    """Temp dir of one pytest *run*: shared by the controller and every xdist worker,
    unique per run (pytest keeps a fresh numbered dir per invocation)"""
    return basetemp.parent if _XDIST_WORKER_BASETEMP_PATTERN.match(basetemp.name) else basetemp


def get_run_token(basetemp: Path) -> str:
    """Token identifying one pytest run: same in every xdist worker, different per run"""
    return f"{get_run_dir(basetemp)}"


def get_run_uid(basetemp: Path) -> str:
    """Short readable identifier of one pytest run (e.g. 'pytest-123'), to keep
    docker objects created outside of the stacks (plain containers) run-scoped as well"""
    return get_run_dir(basetemp).name


def _make_stack_name(git_ref: str, uid: str, suffix: str | None) -> str:
    tail = f"-{suffix}" if suffix else ""
    budget = MAX_STACK_NAME_LEN - len(_STACK_PREFIX) - len(uid) - len("-") * 2 - len(tail)
    readable = _NON_NAME_CHARS.sub("-", git_ref.lower()).strip("-")[:budget].strip("-")
    stack_name = "-".join(part for part in (_STACK_PREFIX, readable, uid, suffix) if part)
    assert len(stack_name) <= MAX_STACK_NAME_LEN
    return stack_name


def compute_stack_names(git_ref: str, run_token: str) -> tuple[str, str]:
    """Returns the (core, ops) stack names for one run

    Both names start with 'pytest-' so test-owned stacks remain easy to spot (and to
    garbage-collect) on a shared daemon.
    """
    uid = hashlib.sha1(run_token.encode(), usedforsecurity=False).hexdigest()[:_UID_LEN]
    core_stack_name = _make_stack_name(git_ref, uid, suffix=None)
    ops_stack_name = _make_stack_name(git_ref, uid, suffix=_OPS_STACK_SUFFIX)
    return core_stack_name, ops_stack_name
