---
applyTo: '**/Makefile,**/*.mk'
---

# Makefile authoring conventions

Full reference: [scripts/makefiles/README.md](../../scripts/makefiles/README.md).

## Naming

- `*.mk` is a library: `include`-only, never run with `make -f`. Shared logic
  lives in `scripts/makefiles/`.
- `Makefile` is an entry point, one per directory, run via `make -C <dir> <target>`.
  Never create a `Makefile` that is only `include`d.
- Each entry point declares its own `.DEFAULT_GOAL`; libraries must not.

## DRY and separation of concerns

- Shared logic lives in exactly one `*.mk`. Do not copy a library recipe into a
  project Makefile.
- Put a recipe in the matching topic library (lint in `python-lint.mk`, install
  in `python-install.mk`, version in `version.mk`, pip-compile in
  `requirements.mk`). If none fits, add a single-purpose `*.mk` instead of
  growing `common.mk`.
- A recipe spanning two topics lives in the library whose topic is named in the
  recipe's primary action (e.g. a pip-compile step that also installs goes in
  `requirements.mk`; an install step that also lints goes in `python-install.mk`).
  The other library delegates via a dependency.
- Package Makefiles include `common.mk` + `package.mk`; service Makefiles include
  `common.mk` + `service.mk`.
- Inside included files, `$(CURDIR)` is the calling project and `REPO_BASE_DIR`
  is the repo root.

## Help output

Follow the [help conventions](../../scripts/makefiles/README.md#help-output-helpmk--helpawk):

- Document public targets with a one-line `##` description starting with a
  capital letter.
- Group related public targets under `##@ Section Name`. Leave helper targets
  (those not documented with `##`) and targets that do not belong to any related
  public-target group unlabeled, i.e. without a `##@` section header.
- Sort targets within a group by name unless execution order matters.
- Never hardcode an emoji, and use a section rather than text such as
  `## [docker] ...`.

## CI contract targets

- Targets invoked by `ci/github/**/*.bash` are a contract: do not rename,
  remove, or change their behavior without updating the caller in the same
  change.
- Mark them `# CI-CONTRACT: <caller>` above the recipe and end their `##`
  description with `[CI]`.
- Before renaming or removing any target, grep `ci/github` for it.

## Removing targets

- Delete a target only if all of the following hold: (1) `grep -r <target> .`
  in the repo finds no references outside its definition, (2) it is not a
  CI-CONTRACT target, and (3) it is not listed in any Makefile's public help.
  Otherwise group it under a `# REVIEW: <reason>` banner for batch review.

## Validating refactors

Compare `make -C <dir> -n <target>` output before and after the change.
