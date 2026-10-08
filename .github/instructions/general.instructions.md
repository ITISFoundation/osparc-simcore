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

- Prefer clear code over comments that repeat it.
- Update docs when a change affects public APIs, configuration, developer
  workflows, deployment, or user-visible behavior. Keep them concise and do not
  duplicate content.

## Ordering

- Keep hand-maintained unordered lists alphabetical. Preserve order that carries
  meaning (precedence, dependency, registration, initialization) and do not
  reorder unrelated entries.
- Where a formatter, linter, or generator owns sorting, use it instead of
  sorting manually.
