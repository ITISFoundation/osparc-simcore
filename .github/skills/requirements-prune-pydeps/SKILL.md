---
name: requirements-prune-pydeps
description: 'Detect and remove unused Python dependencies from a package/service and propagate the cleanup downstream. Use when: pruning requirements, removing unused dependencies, cleaning up `_base.in`/`_test.in`, shrinking install size, fixing leftover deps after refactor, or auditing imports vs declared requirements in osparc-simcore.'
argument-hint: '<package-or-service-path> (e.g. packages/simcore-sdk)'
---

# Prune unused requirements

Over time a package accumulates dependencies that are no longer imported but
remain listed in its `_base.in` / `_test.in`. This skill detects them with
isolated tooling (`uvx deptry`), removes them, recompiles with `uv`, and
propagates the cleanup to dependent services without bumping unrelated packages.

## When to Use

- A package/service lists dependencies that are no longer imported
- After a refactor that removed feature code (and its imports)
- Shrinking production image size by trimming `_base.in`
- Cleaning churny test dependencies in `_test.in`

## Key facts about this repo

- `*.in` files are **hand-edited** sources; `*.txt` files are **generated** by
  `uv pip compile` (via `make reqs`). Never edit `*.txt` directly.
- Compilation chain: `_base.in → _base.txt → _test.in → _test.txt`, with
  `requirements/constraints.txt` applied to every compile.
- **Libraries** (`packages/*`) read deps from `_base.in` in `setup.py`;
  **services** read from the pinned `_base.txt`. So pruning a library's `_base.in`
  affects every downstream service.
- First-party deps (`simcore-*`, `pytest-simcore`) live in `_base.in` as local
  path requirements — tell the scanner about them so they aren't misreported.

## Procedure

### 0. Activate the environment

```bash
which python   # confirm path contains .venv; otherwise:
source .venv/bin/activate
```

### 1. Detect unused dependencies with `deptry` (isolated)

Run **deptry** via `uvx` so nothing is installed into the project venv. It is
purpose-built to report *unused*, *missing*, and *transitive* dependencies in a
single pass and understands `setup.py` / `pyproject.toml`. Mark the repo's
first-party packages as known so intra-repo imports aren't flagged:

```bash
cd packages/simcore-sdk
uvx deptry src \
  --known-first-party simcore_sdk \
  --known-first-party servicelib \
  --known-first-party models_library
```

deptry reports, per category:
- `DEP002` **unused** — declared but never imported → candidates to remove from `_base.in`
- `DEP001` **missing** — imported but undeclared → add to `_base.in`
- `DEP003` **transitive** — imported but only available transitively → declare explicitly

For this skill, act on `DEP002` findings first. `DEP001` and `DEP003` are out
of scope unless they are directly related to a dependency being pruned; otherwise
log them for a separate follow-up task.

> Use `uvx` (ephemeral, isolated) — never `pip install` the scanner into the
> project environment. Optionally cross-check imports with
> `uvx pipreqs --print src/simcore_sdk` (prints only, writes nothing).

If `uvx deptry` fails (e.g., package resolution/network issues or unsupported
layout), fall back to a manual import scan and compare results against declared
dependencies in `requirements/_base.in`:

```bash
grep -rh "^import\|^from" src/ | sort -u
```

### 2. Confirm impact before removing

A package flagged "unused" may still be needed (runtime plugin, CLI entrypoint,
or imported via a string). Inspect what it pulls in transitively, rather than
diffing the compiled `*.txt` afterwards:

```bash
uv pip tree --package <candidate>            # transitive impact of the candidate
grep -rnw 'src' -e '<top_level_import_name>' # is it truly unimported?
```

Then edit `requirements/_base.in` (or `_test.in`) and delete the
confirmed-unused lines.

### 3. Recompile the package

```bash
cd packages/simcore-sdk/requirements
make touch reqs
```

`make reqs` runs `uv pip compile` in an isolated tooling step and regenerates the
`*.txt` files. Inspect the diff: it should only drop the pruned packages and
their now-orphaned transitive deps.

### 4. Propagate downstream with selective recompiles

Find which services/libraries depend on the pruned library:

```bash
grep --include=\*.in -rnw . -e 'packages/simcore-sdk/requirements/_base.in'
```

For each dependent, recompile **only** the affected package(s) so the diff stays
minimal and cleanup is not coupled with unrelated version bumps. Avoid a blanket
`make reqs` that upgrades everything:

```bash
cd services/<dependent>/requirements
make touch
make reqs upgrade=<pruned-or-affected-package>
```

To repin a single package across **all** requirements folders at once, run from
`requirements/tools`:

```bash
cd requirements/tools
make reqs-all startswith=<prefix>     # or  upgrade=<pkg>==<ver>
```

### 5. Validate

```bash
cd packages/simcore-sdk
make install-dev && make tests-unit
```

Repeat for each downstream service whose requirements changed. Confirm the final
`git diff requirements/` contains only the intended removals/partial upgrades.

## Optional: advisory CI guard

To catch leftover dependencies at review time instead of via periodic manual
sweeps, add a **non-blocking** job that runs `uvx deptry src` on changed packages
and posts `DEP002` findings as PR annotations. Keep it advisory — import scanners
produce false positives on plugins and string-imported modules.

## Scope

This skill **completes** when the pruned package and its affected downstream
services compile and pass unit tests. Committing, opening a PR, and full
integration testing are out of scope.

## See also

- [python-dependencies.md](../../../requirements/python-dependencies.md) — dependency model and security workflow
- [how-to-unify-versions.md](../../../requirements/how-to-unify-versions.md)
- [how-to-upgrade-python.md](../../../requirements/how-to-upgrade-python.md)
- [deptry](https://deptry.com/): a CLI tool to check for issues with dependencies in a python project suc as unused or missing dependencies.
