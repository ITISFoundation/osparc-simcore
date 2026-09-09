---
applyTo: '**/Makefile,**/*.mk'
---

# Makefile authoring conventions

The repo's Make system has two layers. Follow these rules when creating or
editing any `Makefile` or `*.mk`. Full reference: [scripts/makefiles/README.md](../../scripts/makefiles/README.md).

## Naming (the invariant)

- `*.mk` = **library**: `include`-only, never invoked directly. Put reusable
  logic here, under `scripts/makefiles/`.
- `Makefile` = **entry point**: invoked as `cd <dir> && make <target>` or
  `make -C <dir> <target>` by a human or CI. One `Makefile` per directory
- Never create a `Makefile` that is only `include`d. The `make -f` option
  selects a file as Make's entry point, so do not use it to execute a shared
  `.mk` library. Include libraries from a project `Makefile` instead.
- Each entry-point `Makefile` declares its own `.DEFAULT_GOAL`. Shared `.mk`
  libraries must not impose a default target on their callers.

## DRY & separation of concerns

- Shared logic lives in exactly one `*.mk` and is `include`d — do not copy a
  recipe into a project Makefile that a library already provides.
- Place a recipe in the topic library that matches it (examples: lint →
  `python-lint.mk`, install → `python-install.mk`, version → `version.mk`,
  pip-compile → `requirements.mk`). If none fits, add a new single-purpose
  `*.mk` containing only targets for that topic (no more than one logical
  concern per file) rather than bloating `common.mk`.
- If a recipe legitimately spans two topics, place it in the more specific
  topic library and have the other library delegate to it via a dependency,
  rather than duplicating the recipe.
- A package Makefile includes at least `common.mk` + `package.mk`; a service Makefile
  includes at least `common.mk` + `service.mk`. A directory may include additional
  topic libraries when its targets need them.

## Recipe organization within a `.mk` file

- **Group related recipes**: A public target is a user-invoked target documented
  with `##`. A group is two or more public targets that share a user-facing
  purpose or workflow, such as `mypy` and `mypy-debug`. Keep them together when
  that makes the Makefile or `make help` easier to scan.
- **Label useful groups**: Put `##@ Section Name` above a group when the
  section name helps users find those targets in `make help`. A single target
  may have a section when the category is meaningful, but do not create a
  section just to label one unrelated target.
- **Leave small or internal blocks unlabeled**: Sections are optional. Pattern
  rules, prerequisites, private helpers, and isolated public targets do not
  need `##@` headers. They remain in the leading unlabeled help section when
  they have a `##` description.
- **Organize groups alphabetically**: Within a group, sort public targets by
  name when their order has no semantic meaning, for example `check`, `clean`,
  `help`, and `reqs`. Keep dependency or execution order when it matters.
- **Implementation comments are separate**: `# -----------...` comments can
  separate code sections for readers, but only `##@ Section Name` controls
  grouping in the shared help renderer.
- **See example**: `scripts/makefiles/python-lint.mk` uses `##@` headers to
  separate main linting targets from developer convenience targets while
  keeping `mypy` and `mypy-debug` together.

## CI contract targets

- Targets invoked by `ci/github/**/*.bash` are a **contract**: their name and
  observable behavior must not change without updating the caller in the same
  change. Mark them `# CI-CONTRACT: <caller>` above the recipe.
- Append `[CI]` to the end of a CI-contract target's `##` help description.
- Before renaming/removing any target, grep `ci/github` for its name.
- Known contract targets: `install-ci`, `test-ci-unit`, `test-ci-integration`,
  `tests-ci`, `mypy`, `pylint`, and root `devenv` / `openapi-specs` /
  `info-images` / `down` / `leave` / `pull-externals`.

## Help output & grouping

- `scripts/makefiles/help.mk` (delegating to `scripts/makefiles/help.awk`) is
  the shared `make help` renderer. It is included by `common.mk` for every
  package/service, and directly by the root `Makefile`.
- The shared help renderer requires GNU `gawk` because it sorts targets with
  `asort()`.
- Add a `##@ Section Name` comment above a group of targets to label it in
  `make help`. It applies to every target below it until the next `##@` line
  in that file.
- **Help text must start with a capital letter** (e.g., `## Runs mypy...` not
  `## runs mypy...`). This applies to all `##` descriptions across all
  Makefiles and `.mk` files.
- **Help text must fit on a single line** — keep descriptions concise and avoid
  line breaks within the `##` comment.
- The same section name reused across different files merges into a single
  section in the output (e.g. `##@ Tests` in both `service.mk` and
  `package.mk`) — this is how related targets stay grouped regardless of
  `include` order.
- Targets with no `##@` above them fall into a leading, unlabeled section —
  no migration is required for Makefiles that don't opt in.
- `help.awk` assigns a small icon by keyword/substring match on the section
  name (e.g. any name containing "Docker", "Test", "Lint", "Clean",
  "Environment"/"Install", "i18n", "Version"/"Release", "Swarm"/"Container",
  "Info"/"Misc"). This table is centralized in `help.awk` — never hardcode an
  emoji in a `##` description or `##@` header text.
- Prefer a real `##@` section over ad-hoc category text in the description
  (e.g. don't write `## [docker] builds ...`; put the target under `##@
  Docker` instead). `[CI]` is unrelated to grouping and stays as documented
  above.

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
