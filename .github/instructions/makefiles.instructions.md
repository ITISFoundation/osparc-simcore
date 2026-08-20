---
applyTo: '**/Makefile,**/*.mk'
---

# Makefile authoring conventions

The repo's Make system has two layers. Follow these rules when creating or
editing any `Makefile` or `*.mk`. Full reference: `scripts/makefiles/README.md`.

## Naming (the invariant)

- `*.mk` = **library**: `include`-only, never invoked directly. Put reusable
  logic here, under `scripts/makefiles/`.
- `Makefile` = **entry point**: invoked as `cd <dir> && make <target>` by a
  human or CI. One per project directory + the repo root.
- Never create a `Makefile` that is only `include`d, and never `make -f a.mk`.

## DRY & separation of concerns

- Shared logic lives in exactly one `*.mk` and is `include`d — do not copy a
  recipe into a project Makefile that a library already provides.
- Place a recipe in the topic library that matches it (lint →
  `python-lint.mk`, install → `python-install.mk`, version → `version.mk`,
  pip-compile → `requirements.mk`). If none fits, add a small new topic `*.mk`
  rather than bloating `common.mk`.
- A package Makefile includes `common.mk` + `package.mk`; a service Makefile
  includes `common.mk` + `service.mk`.

## CI contract targets

- Targets invoked by `ci/github/**/*.bash` are a **contract**: their name and
  observable behavior must not change without updating the caller in the same
  change. Mark them `# CI-CONTRACT: <caller>` above the recipe.
- Before renaming/removing any target, grep `ci/github` for its name.
- Known contract targets: `install-ci`, `test-ci-unit`, `test-ci-integration`,
  `tests-ci`, `mypy`, `pylint`, and root `devenv` / `openapi-specs` /
  `info-images` / `down` / `leave` / `pull-externals`.

## Dead / uncertain targets

- Only delete a target if it is clearly unused. Otherwise group it under a
  `# REVIEW: <reason>` banner (with no known CI/docs callers) so it can be
  reviewed as a batch — do not silently drop it.

## Variables available inside included files

- `$(CURDIR)` = the calling project's directory (not the `.mk`'s location).
- `REPO_BASE_DIR` (from `globals.mk`) = repo root; use it for repo-relative
  includes and config paths.

## Validate behavior-preserving edits

Confirm a refactor does not change output with a dry-run diff, e.g.:

```bash
make -C <dir> -n <target>   # compare before/after (stash the change for "before")
```
