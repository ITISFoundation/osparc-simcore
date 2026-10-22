"""Names of the docker objects the integration tests deploy.

Stack and service names are global inside a docker daemon, so two pytest sessions running
from different checkouts of this repo on one machine (e.g. two git worktrees) must not deploy
under the same names. Every checkout deploys its stacks under its dev slot
(``pytest-s<N>-{core,ops}``, see pytest_simcore.helpers.dev_slot and scripts/dev_slot.py).

Stack names stay within ``MAX_STACK_NAME_LEN`` so that the names ``docker stack deploy``
derives from them (``{stack}_{service}`` and ``{stack}_{network}``) each remain a valid
single DNS label.
"""

import hashlib
from pathlib import Path
from typing import Final

# "docker stack deploy" names both its services ("{stack}_{service}", also the overlay
# network alias) and its networks ("{stack}_{network}"), which must each fit in one DNS
# label (<= 63 chars); the longest name deployed by the tests is the network
# "computational_services_subnet" (29 chars, see services/docker-compose.yml)
MAX_STACK_NAME_LEN: Final[int] = 63 - len("_") - len("computational_services_subnet")

_UID_LEN: Final[int] = 4


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
