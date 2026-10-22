# Parallel checkouts on one docker daemon

Stack, network, volume and image names and host ports are global in a docker
daemon. To run several checkouts of this repo at once (e.g. git worktrees),
each checkout leases a **dev slot** `N` from 0 to 9.

Slot 0 uses the same names and ports as before slots existed. Slot `N > 0`
uses:

- dev stacks: `simcore-sN`, `ops-sN`, `vendors-sN`
- test stacks: `pytest-sN-<branch>-core`, `pytest-sN-<branch>-ops` in every
  slot, with the branch cut to 18 characters
- traefik zone: `internal_simcore_stack_sN`
- local images: `local/<service>:production-sN`, `development-sN`
- frontend compiler container: `qooxdoo-compiler-sN`
- host ports: slot-0 port + `N*100`, e.g. 9381 instead of 9081 in slot 3

## Usage

`make .env` and the `up-*` targets lease the slot and write it to `.env` as
`OSPARC_DEV_SLOT`. The first checkout gets slot 0, later ones the lowest free
slot.

In a new worktree, the first `make` stops after creating `.env` with
"this checkout now holds dev slot N ... re-run make". Run it again.

- `make info` shows this checkout's slot and the owners of the other slots.
- `make up-*` prints the endpoints with this slot's ports.
- `make down` removes only this checkout's stacks.
- `make leave` refuses while other checkouts have stacks, unless `force=1`.
- `slot=N` moves the checkout to slot `N`, e.g. `make up-devel slot=2`.
- `make -C .vscode launch.json` writes the debugger configs with this slot's
  ports. Delete the old `launch.json` first.
- Images are tagged per slot, so build them in each checkout. The build cache
  is shared.

The integration tests use the checkout's slot as well. They stop with an
error while this checkout's dev stack is up (run `make down`). Tests of other
checkouts are not affected. Test stacks of the slot left from another branch
are removed before deploying.

## Slot markers

Slot `N` is held by the config-only docker network `osparc-dev-slot-N`,
labelled with the checkout path. Network names are unique, so creating it is
atomic. Each lease removes the markers of deleted checkouts. The code is in
[scripts/dev_slot.py](../scripts/dev_slot.py); pytest loads the same file.

Shared between slots: the swarm, the build cache and the test registry
`pytest_registry_v3` on port 5000.

All worktrees also share the git hooks. `make devenv` therefore installs
pre-commit as a uv tool (`~/.local/bin/pre-commit`) and installs the hook from
there, so the hook does not depend on the `.venv` of one worktree.

If the marker is lost (e.g. `docker network prune`) and another checkout takes
the slot, `make` stops with "this checkout now holds dev slot ...". Re-run it
and rebuild the images.
