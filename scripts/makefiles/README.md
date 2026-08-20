# Makefile infrastructure (`scripts/makefiles/`)

This directory holds the **reusable Make libraries** that back every package and
service Makefile in the repo. It exists to keep local and CI workflows DRY and
consistent.

## The one invariant

| Extension | Role | Invoked how | Lives where |
|---|---|---|---|
| `*.mk` | **library** | `include`-only, never called directly | `scripts/makefiles/` |
| `Makefile` | **entry point** | `cd <dir> && make <target>` (human or CI) | each project root + repo root |

If you find yourself running `make -f something.mk`, it should have been a
`Makefile`. If you find a `Makefile` that only gets `include`d, it should have
been a `*.mk`.

## Library layout & responsibilities

```
scripts/makefiles/
├── common.mk          # aggregator included by EVERY package/service Makefile
│   ├── globals.mk     # OS/platform detection, colors, VCS vars, REPO_BASE_DIR, paths, venv checks
│   ├── templates.mk   # clone_from_template macro (used by `.env`)
│   ├── help.mk        # auto-documented `help` target
│   ├── python-lint.mk # pylint / ruff / mypy / codestyle (+ REVIEW-tagged extras)
│   └── version.mk     # version-{patch,minor,major} (bump2version)
├── package.mk         # profile for packages/  (adds package vars + i18n)
├── service.mk         # profile for services/  (adds docker/openapi + tests + install)
│   └── python-install.mk  # shared install-{dev,prod,ci}
├── requirements.mk    # pip-compile workflow for every <project>/requirements/Makefile
├── i18n.mk            # user_message() extraction
└── ollama.mk          # local Ollama daemon helpers (used by scripts/ollama)
```

Include order in a **package** Makefile:

```make
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/package.mk
```

Include order in a **service** Makefile:

```make
include ../../scripts/makefiles/common.mk
include ../../scripts/makefiles/service.mk
```

Every `<project>/requirements/Makefile` includes the pip-compile library
directly:

```make
include ../../../scripts/makefiles/requirements.mk
```

## CI is a contract

Some targets are invoked by `ci/github/**/*.bash`. Their **name and behavior are
a contract** shared with those scripts. They are tagged in the source:

```make
# CI-CONTRACT: install-ci is invoked by ci/github/**/*.bash
install-dev install-prod install-ci: _check_venv_active
```

Rules for a `# CI-CONTRACT` target:

- Do **not** rename, remove, or change its observable behavior without updating
  the calling CI script(s) **in the same change**.
- Contract targets today: `install-ci`, `test-ci-unit`, `test-ci-integration`
  (services), `tests-ci` (packages), `mypy`, `pylint`, plus root-level
  `devenv`, `openapi-specs`, `info-images`, `down`, `leave`, `pull-externals`.

## `# REVIEW` markers

Developer-only convenience targets with **no known CI or docs callers** are
grouped under `# REVIEW` banners (e.g. in `python-lint.mk` and `service.mk`:
`codeformat`, `pyupgrade`, `doc-uml`, `mypy-debug`, `check-test-dispatch`,
`pip-freeze`). They are kept for now; remove them as a batch once confirmed
unused.

## Conventions for changing these files

1. **DRY**: shared logic lives in exactly one `*.mk` and is `include`d. Don't
   copy a recipe into a project Makefile that a library already provides.
2. **Separation of concerns**: put a recipe in the library that matches its
   topic (lint → `python-lint.mk`, install → `python-install.mk`, …). If none
   fits, prefer a new small topic `*.mk` over bloating `common.mk`.
3. **`$(CURDIR)` is the caller's dir** inside every included file — rely on it
   for project-relative paths.
4. **`REPO_BASE_DIR`** (from `globals.mk`) is the repo root; use it for
   repo-relative includes and config paths.
5. Before changing a contract target, grep `ci/github` for its name.
6. Validate a change is behavior-preserving with a dry-run diff:
   `diff <(git stash -u -- scripts requirements; make -C <dir> -n <target>; git stash pop) ...`

## Known follow-ups (deferred, need manual review)

- **Package test/install DRY**: `packages/*/Makefile` still each define their own
  `install-*` / `tests` / `tests-ci` / `requirements`. These have **drifted** and
  cannot be blanket-shared without changing behavior:
  - `celery-library` adds `--keep-docker-up` to `tests`/`tests-ci`.
  - `common-library` omits `--junitxml` in `tests-ci` and has a **custom**
    `install-dev` that compiles locale `.mo` files.
  - `postgres-database` covers `simcore_postgres_database` (folder name differs).
  - `simcore-sdk` uses `tests-unit-ci` / `tests-integration-ci` (has integration).
  - `service-library` uses `install-%` / `test-*[extras]` bracket variants.
  Reconciling this needs a per-package decision (parametrize a shared recipe with
  `--keep-docker-up` / `--junitxml` toggles + an overridable cov target), which is
  why it was **not** auto-applied.
