---
name: chore-propagate-security-fix
description: 'Apply a security constraint for a vulnerable Python package and re-pin it across every requirements file in the osparc-simcore monorepo. Use when: fixing a CVE/GHSA advisory, responding to a pip-audit or Dependabot security alert, patching a vulnerable dependency repo-wide, adding a constraint to requirements/constraints.txt, or bumping a package across all *.txt files at once.'
argument-hint: '<package> <constraint> [<cve-id>] (e.g. aiohttp ">=3.11.14" CVE-2024-23334)'
---

# Propagate a security fix repo-wide

A CVE/GHSA advisory against a Python dependency must be patched **everywhere**
it is pinned, not in a single service. This skill adds a global constraint to
`requirements/constraints.txt` and re-pins the package across all 35+
`requirements/*.txt` files in one pass, using the bundled
[propagate-security-fix.sh](./scripts/propagate-security-fix.sh) script.

This is a **repository-wide** maintenance task — it is not scoped to any single
package or service.

## When to Use

- A `pip-audit` CI run or Dependabot alert reports a CVE in a production dependency
- A GHSA advisory requires a minimum safe version of a shared library
- You need the same minimum version enforced across the entire monorepo
- After triaging an advisory and confirming the fixed version exists on PyPI

## Key facts about this repo

- `requirements/constraints.txt` holds **global** pins (vulnerabilities, breaking
  changes, coordination) applied to every `uv pip compile` in the repo.
- `*.txt` files are **generated**; never edit them by hand. The script regenerates
  them via `make -C requirements/tools reqs-all upgrade=<package>`.
- Security fixes have **no cool-down / N-1 delay** — apply immediately once the
  fixed version is verified on PyPI (see the policy in
  [.github/dependabot.yml](../../dependabot.yml)).
- Vulnerability constraints are conventionally annotated with their advisory id,
  e.g. `aiohttp>=3.11.14  # security: CVE-2024-23334`.

## Procedure

### 0. Activate the environment

```bash
which python   # confirm path contains .venv; otherwise:
source .venv/bin/activate
```

Ensure `uv` is installed and you are at the repo root.

### 1. Triage the advisory

Before running anything, confirm:
- The **package name** as it appears in `requirements/constraints.txt`.
- The **minimum safe version** from the CVE/GHSA advisory.
- That the fixed version is **published on PyPI**.
- The **advisory id** (`CVE-…` or `GHSA-…`) to annotate the constraint.

### 2. Run the propagation script

```bash
.github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh <package> <constraint> [<cve-id>]

# Example:
.github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh aiohttp ">=3.11.14" CVE-2024-23334

# Non-interactive (CI / agent): replace an existing constraint without prompting
.github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh --yes aiohttp ">=3.11.14" CVE-2024-23334
```

The script:
1. Validates the package name and the PEP-440 constraint operator.
2. Adds or updates the pin in `requirements/constraints.txt` (annotated with the
   advisory id). If a constraint for the package already exists, it prompts before
   replacing it — pass `--yes` (or `-y` / `--force`) to skip the prompt.
3. Runs `make -C requirements/tools reqs-all upgrade=<package>` to re-pin the
   package across every `requirements/*.txt` file.
4. Prints the list of changed files and a ready-made `git commit` command.

> If the package already has a constraint, the script asks for confirmation
> before replacing it. A non-interactive shell that declines the prompt exits
> without changes — re-run with `--yes` to replace an existing pin unattended.

### 3. Validate

```bash
git diff requirements/                       # review constraint + re-pinned *.txt
grep -n "<package>" requirements/constraints.txt
make tests-unit                              # or targeted tests for affected services
```

Confirm the new lower bound appears in the affected `*.txt` files and that
nothing unrelated was bumped.

### 4. Commit

```bash
git add requirements/
git commit -m 'fix(deps): <package><constraint> (<cve-id>)'
```

## Related triggers in CI

- [.github/workflows/pip-audit.yml](../../workflows/pip-audit.yml) scans `*_base.txt`
  for advisories and links to this workflow in its report.
- [.github/dependabot.yml](../../dependabot.yml) documents the security workflow and
  cool-down policy (version updates are disabled because Dependabot cannot edit the
  generated `*.txt` files).
- [requirements/python-dependencies.md](../../../requirements/python-dependencies.md)
  describes the security-fix SLA and applying-a-fix steps.
