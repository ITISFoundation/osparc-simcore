# Parallel checkouts (git worktrees) on one docker daemon

Stack, network, volume and image names and host-published ports are global
inside a docker daemon. To develop and test in several checkouts of this repo
at once (typically `git worktree add ../osparc-simcore-feature-x`), every
checkout uses its own numbered **dev slot** `N` (0–9).

Slot 0 is exactly the layout used before slots existed: a single checkout sees
no change. Slot `N > 0` derives its names and ports from `N`:

- dev stacks (`make up-*`): `simcore-sN`, `ops-sN`, `vendors-sN`
  (slot 0: `master-simcore`, `ops`, `vendors`)
- test stacks (pytest): `pytest-sN-core`, `pytest-sN-ops`
- traefik zone: `internal_simcore_stack_sN`
- local images (`make build*`): `local/<service>:production-sN`
  and `local/<service>:development-sN`
- frontend compiler container: `qooxdoo-compiler-sN`
- host ports: the slot-0 port `+ N*100`
  (e.g. 9381, 9301 and 3301 in slot 3 instead of 9081, 9001 and 3001)

## Usage

Nothing to do. `make .env` (a prerequisite of the build and deploy targets)
and every `up-*` target lease the slot of the checkout automatically and cache
it in `.env` as `OSPARC_DEV_SLOT`. The first checkout gets slot 0, the next
one the lowest free slot.

In a new worktree, the very first `make` that creates `.env` stops once with
"this checkout now holds dev slot N ... re-run make": it ran with the default
slot before the lease, so just re-run it.

- `make info` shows the slot of this checkout and which checkout holds the
  other slots.
- After `make up-*`, the endpoint table lists the URLs with this slot's ports.
- `make down` only removes this checkout's stacks. `make leave` refuses while
  stacks of other checkouts (or test runs) are deployed, unless `force=1`.
- To move a checkout to a given slot, pass `slot=N` to any target,
  e.g. `make up-devel slot=2`.
- VS Code: `make -C .vscode launch.json` renders the "Python: Remote Attach"
  configs with this slot's debug ports (delete an existing `launch.json`
  first).
- Images are tagged per slot: build them in each checkout (`make build` /
  `make build-devel`). The docker build cache is shared.

Integration tests (pytest) deploy under the checkout's slot too. They
therefore cannot run while the dev stack of the **same** checkout is up (they
stop with an explicit message: run `make down` first). Tests of different
checkouts run side by side.

## How slots are held

The registry of leased slots is the docker daemon itself: slot `N` is held by
a config-only network `osparc-dev-slot-N` (no driver, no address space)
labelled with the checkout path. Network names are unique, so creating it is
an atomic lease. Markers of checkouts that no longer exist (deleted worktrees)
are removed on the next lease, which frees their slot.

All of this lives in [scripts/dev_slot.py](../scripts/dev_slot.py) (stdlib
only); pytest uses the same file (`pytest_simcore.helpers.dev_slot`).

Shared on purpose: the swarm itself (see
`pytest_simcore.helpers.swarm_coordination`), the docker build cache and the
test registry `pytest_registry_v3` on host port 5000.

If the slot cached in `.env` gets out of sync (e.g. the marker was pruned by
`docker network prune` and another checkout took the slot), `make` stops with
"this checkout now holds dev slot ...": re-run it, and rebuild the images for
the new slot.
