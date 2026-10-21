---
applyTo: '**'
---

# General repository conventions

This repository is a monorepo of Python microservices and JavaScript frontends.
Use the Python version in the root `.python-version` file. Do not use syntax
or standard-library features unavailable in that version.
Apply all instruction files whose `applyTo` patterns match the file you are
editing. Where matching instructions conflict, prefer the rule specific to
that file type or service over a general rule.

## Change discipline

- Keep changes focused on the requested behavior. Avoid unrelated refactors,
  formatting churn, or reordering.
- Change generated, vendored, or lock files only when the task requires it.
  Use the generation command documented in the file's header or the owning
  package or service's `README.md`.
- Do not add real secrets or credentials, including tokens and private keys,
  production endpoints, or environment-specific configuration to tracked files,
  fixtures, logs, or user-visible errors. Test fixtures may contain clearly
  synthetic credentials or credentials generated only for disposable local
  test resources. Never copy credentials from real environments into tests.

## Configuration

- Follow the [Environment Variables Guide](../../docs/env-vars.md) for
  configuration changes. Do not introduce ad hoc configuration mechanisms.
- When adding configuration, update validation, safe examples and defaults,
  deployment configuration, and tests as applicable.

## Tests and validation

- For behavior changes, add or update automated tests at the appropriate level.
  Use unit tests for pure logic, integration tests for database or service
  boundaries, API or contract tests for changed HTTP or message interfaces,
  component tests for frontend components, and end-to-end tests only for
  user-visible flows that span services. Prefer unit tests to slow integration
  or end-to-end tests.
- Prefer behavior-focused tests over tests coupled to private implementation.
  Avoid tautological assertions. Derive expected results from the required
  behavior or an independent reference, not by calling the implementation under
  test or copying its algorithm. Mock dependencies, not the behavior being
  tested. Checking only a mock's configured return value does not validate it.
- For a bug fix, add a regression test that fails before the fix and passes
  after it. If no such test is feasible, state the reason in the final chat
  response to the user under a heading named 'Validation'.
- Run the narrowest relevant validation available. Report which tests or checks
  you did not run and why.
- Run `pre-commit run --files <changed files>` and fix all
  findings. Never commit with `--no-verify`. If a pre-commit hook fails, fix
  the findings or explain them; do not bypass the hook.
- If a hook fails on pre-existing violations in a touched file, verify that
  your diff introduces zero new violations (compare `ruff check` output
  against `git show HEAD:<file> | ruff check --stdin-filename <file> -`) and
  fix every newly introduced violation before committing.

## Documentation

- Prefer clear code over comments that repeat it. Write comments in plain,
  specific language about intent, constraints, or non-obvious behavior. Omit
  boilerplate, decorative headings, and step-by-step narration.
- Update docs when a change affects public APIs, configuration, developer
  workflows, deployment, or user-visible behavior.
- Keep docs concise. Link to existing explanations rather than copying them.
  Retain brief local context where needed to understand or use the code.

## Git workflow

- Commit locally and stop. Do not push, force-push, create pull requests, or
  resolve review threads unless explicitly asked.
- Address code-review comments in new commits (e.g. `fix(review): ...`), never
  by amending the reviewed commit, so reviewers can see the incremental fix.
- Create pull requests as drafts unless explicitly told otherwise. If intent
  is unclear, ask.

## Pull request descriptions

- Follow the structure of [PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md).
- Keep them compact: state the final solution, the facts, and the
  measurements. No trial or process narrative, no step-by-step history of how
  the branch evolved.
- Performance PRs: include before/after measurements (e.g. CI step durations,
  baseline mean vs. new value). If the measurement is not available yet, leave
  an explicit placeholder and fill it in once CI completes.

## Ordering

- Insert new entries into hand-maintained unordered lists in alphabetical
  position. Do not reorder existing entries. Preserve order that affects
  behavior, such as precedence, dependencies, registration, or initialization.
- Use the configured formatter, linter, or generator to sort entries when it
  provides that function.
