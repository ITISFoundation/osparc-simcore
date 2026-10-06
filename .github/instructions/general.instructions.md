---
applyTo: '**'
---

This repository is a monorepo of Python microservices and JavaScript frontends.
Python version requirements are defined in `.python-version`. Follow the closest
applicable scoped instruction file in addition to these repository-wide rules.

## Change discipline

- Keep changes focused on the requested behavior. Avoid unrelated refactors,
  formatting churn, or reordering.
- Do not modify generated, vendored, or lock files unless the task requires it
  and the documented generation workflow is used.
- Do not add secrets, credentials, tokens, private keys, production endpoints,
  or environment-specific configuration to tracked files, fixtures, logs, or
  user-visible errors.

## Configuration

- Follow the [Environment Variables Guide](../../docs/env-vars.md) for
  configuration changes. Do not introduce ad hoc configuration mechanisms.
- When adding configuration, update validation, safe examples/defaults,
  deployment configuration, and tests as applicable.

## Tests and validation

- For behavior changes, add or update automated tests at the appropriate level:
  unit, integration, API/contract, component, or end-to-end.
- Prefer behavior-focused tests over tests coupled to private implementation.
- For a bug fix, add a regression test when practical.
- Run the narrowest relevant validation available. Report tests or checks that
  were not run and why.

## Documentation

- Prefer clear code over comments that repeat the implementation.
- Update documentation when behavior changes affect public APIs, configuration,
  developer workflows, deployment, user-visible behavior, or non-obvious
  invariants.
- Keep documentation concise; do not duplicate content or add commentary that
  does not help users or maintainers.

## Ordering

- Keep hand-maintained unordered lists in alphabetical order unless the order
  carries semantic meaning (e.g. dependency ordering, priority, registration,
  initialization).
- Preserve intentional ordering and grouping. Do not reorder unrelated entries as
  cleanup. When a file has an established formatter, linter, generator, or
  repository convention for sorting, use that mechanism rather than sorting
  manually.
- File-type-specific ordering conventions live in the applicable scoped
  instruction file.
