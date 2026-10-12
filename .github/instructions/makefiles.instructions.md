---
applyTo: '**/Makefile,**/*.mk'
---

# Makefile authoring conventions

See
[scripts/makefiles/README.md](../../scripts/makefiles/README.md)
for the full reference.

## Naming

- A `*.mk` file is a library. Load it with `include`, never with `make -f`.
  Shared libraries live in `scripts/makefiles/`.
- A `Makefile` is an entry point. Use one per directory and run it with
  `make -C <dir> <target>`. Never create a `Makefile` used only through `include`.
- Each entry point declares its own `.DEFAULT_GOAL`. Libraries must not.

## Shared recipes

- Shared logic lives in exactly one `*.mk`. Do not copy a library recipe into a
  project Makefile.
- Put recipes in the matching topic library. Use `python-lint.mk` for linting,
  `python-install.mk` for installation, `version.mk` for version handling, and
  `requirements.mk` for pip-compile. If none fits, add a single-purpose `*.mk`
  instead of adding the recipe to `common.mk`.
- For a recipe with two topics, choose the library that matches its primary
  action. A pip-compile step that also installs belongs in `requirements.mk`.
  An install step that also lints belongs in `python-install.mk`.
  The other library calls it through a dependency.
- Package Makefiles include `common.mk` and `package.mk`. Service Makefiles
  include `common.mk` and `service.mk`.
- Inside included files, `$(CURDIR)` is the calling project and `REPO_BASE_DIR`
  is the repo root.

## Help output

Follow the [help conventions](../../scripts/makefiles/README.md#help-output-helpmk--helpawk):

- Document public targets with a one-line `##` description starting with a
  capital letter.
- Group related public targets under `##@ Section Name`. Do not add a `##@`
  section header for helper targets without `##` descriptions or for targets
  that do not belong to a group of related public targets.
- Sort targets within a group by name unless execution order matters.
- Never hardcode an emoji, and use a section rather than text such as
  `## [docker] ...`.

## CI contract targets

- Scripts in `ci/github/**/*.bash` depend on the targets they invoke.
  Do not rename or remove those targets, or change their behavior, without
  updating the caller in the same change.
- Mark them `# CI-CONTRACT: <caller>` above the recipe and end their `##`
  description with `[CI]`.
- Before renaming or removing any target, grep `ci/github` for it.

## Removing targets

- Before deleting a target, run `grep -r <target> .` in the repository.
  Delete it only if the search finds no references outside its definition,
  it is not a CI-CONTRACT target, and no Makefile lists it in public help.
  Otherwise, group it under a `# REVIEW: <reason>` comment for batch review.

## Validating refactors

Compare `make -C <dir> -n <target>` output before and after the change.
