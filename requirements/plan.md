# Dependency security workflow — improvement plan

Current status and roadmap for the Python dependency management and security
scanning infrastructure in this repo.

---

## What was implemented (June 2026)

### `.github/workflows/pip-audit.yml`
Automated CVE scanning for all 35 `_base.txt` (fail on CVE) and 35 `_test.txt`
(warn only) files. Runs weekly + on PRs that touch any requirements file.
Uploads SARIF to the GitHub Security tab and writes a markdown step summary.

### `.github/dependabot.yml` — reworked
| Change                                          | Reason                                                                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Removed stale `ignore:` entries (2021-era)      | docker-compose 1.28.x, idna 3.1, httpx 0.17.0, openapi-core — no longer relevant                       |
| `open-pull-requests-limit: 0` for pip           | `.txt` files are generated artifacts; direct Dependabot edits would be overwritten by `uv pip compile` |
| Added `cooldown:` to `github-actions`           | patch=7d / minor=14d / major=30d; security bypasses automatically                                      |
| Added `docker` ecosystem entry (21 Dockerfiles) | Tracks `python:X.Y-slim-bookworm` and uv base images; same cooldown policy                             |

### `scripts/propagate-security-fix.sh`
Interactive script: given a package name, version constraint, and optional CVE
id, it updates `requirements/constraints.txt` and reruns `make reqs-all
upgrade=<package>` repo-wide. See `python-dependencies.md § Security workflow`
for the full usage guide.

---

## Remaining work — near term

### 1. Validate the pip-audit workflow on CI (low effort)
Open a draft PR on branch `mai/reqs` and verify the workflow runs green.
Check that the SARIF upload appears in the Security tab and that the markdown
summary renders in the job log. Adjust `--skip-editable` / `--no-deps` flags if
pip-audit chokes on path dependencies inside the `*.txt` files.

### 2. Audit `requirements/constraints.txt` for stale entries (low effort)
Several pins in the file reference old issues or bugs that may have been
resolved. Systematically go through each entry, check whether the constraint is
still necessary with current package versions, and remove or relax those that
are no longer needed. This reduces false friction during upgrades.

### 3. Wire the Security tab SARIF into PR checks (medium effort)
Configure a branch protection rule or `code-scanning` required check so that
uploading SARIF findings with `level: error` actually blocks PR merge. Without
this the SARIF upload is informational only.

### 4. Add `_tools.txt` to pip-audit scope (low effort)
The current workflow scans `_base.txt` (fail) and `_test.txt` (warn). A third
tier — `_tools.txt` — also exists in some packages. Decide on a policy (warn or
fail) and add a third matrix entry to the workflow.

---

## Remaining work — medium term

### 5. Document the cool-down policy for Python libraries in ADR / CHANGELOG
The N-1 / patch-lag policy for strategic Python libs (pydantic, aiohttp,
sqlalchemy, etc.) is currently described only in `python-dependencies.md`. A
short ADR (`docs/adr/`) or CONTRIBUTING note would make it discoverable for
contributors who don't read the full doc.

### 6. Evaluate Renovate as an alternative to Dependabot for pip (medium effort)
Renovate supports `uv` natively (lockfile-aware), can open grouped PRs, and
understands the `.in` → `.txt` compilation pattern via custom managers. The
main limitation is that it requires either the Renovate GitHub App or a
self-hosted runner. Worth evaluating if the number of manual pip upgrade cycles
increases. Key comparison points:
- Renovate can run `uv pip compile` as a post-upgrade command, producing correct
  `*.txt` output directly in the PR.
- Dependabot cannot; hence the current `open-pull-requests-limit: 0` workaround.

### 7. Add SBOM generation to the release pipeline (medium effort)
Generate a Software Bill of Materials (CycloneDX or SPDX format) from the
frozen `_base.txt` files as part of the Docker image build or release workflow.
This is increasingly required by enterprise customers and supply-chain
regulations. `pip-audit --format cyclonedx` or `cyclonedx-bom` are lightweight
options that integrate well with the existing CI structure.

### 8. Automated PR for constraint bumps after a CVE fix (medium effort)
Currently `propagate-security-fix.sh` requires a developer to run it manually.
A GitHub Actions workflow that triggers on a Dependabot security alert (via
`dependabot` event) could automate steps 2-3 of the fix workflow:
1. Parse the alert payload to get `package` + `safe_version`.
2. Run `propagate-security-fix.sh` inside a workflow job.
3. Open a PR with the updated `constraints.txt` + regenerated `*.txt` files.

---

## Deferred / out of scope

- **Automated full upgrades via CI**: periodically regenerating all `*.txt`
  files to their latest allowed versions. Currently done manually. Could be
  automated as a weekly scheduled PR, but requires careful testing gates to
  avoid noise.
- **`pip-sync` enforcement**: ensuring installed packages in dev envs exactly
  match `*.txt`. Currently only recommended in the doc; no enforcement exists.
- **Dependency graph visualization**: `pydeps` is already in tooling but not
  integrated into PR checks or dashboards.
