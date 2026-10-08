---
applyTo: '**'
---

This repository is a monorepo of Python microservices and JavaScript frontends.
Python version requirements are defined in `.python-version`. Apply the scoped
instruction file whose directory is the nearest ancestor of the file being
edited. If a scoped file conflicts with this file, the scoped file takes
precedence.

## Change discipline

- Keep changes focused on the requested behavior. Avoid unrelated refactors,
  formatting churn, or reordering.
- Do not modify generated, vendored, or lock files unless the task requires it
  and the generation command documented in the generated file's header or in the
  `README.md` of the owning package or service is used.
- Do not add secrets, credentials, tokens, private keys, production endpoints,
  or environment-specific configuration to tracked files, fixtures, logs, or
  user-visible errors.

## Configuration

- Follow the [Environment Variables Guide](../../docs/env-vars.md) for
  configuration changes. Do not introduce ad hoc configuration mechanisms.
- When adding configuration, update validation, safe examples/defaults,
  deployment configuration, and tests as applicable.

## Tests and validation

- For behavior changes, add or update automated tests at the appropriate level.
  Use unit tests for pure logic, integration tests for database or service
  boundaries, API/contract tests for changed HTTP or message interfaces,
  component tests for frontend components, and end-to-end tests only for
  user-visible flows that span services. Prefer unit tests to slow integration or end-to-end tests.
- Prefer behavior-focused tests over tests coupled to private implementation.
- For a bug fix, add a regression test that fails before the fix and passes
  after it. If no such test is feasible, state the reason in the summary.
- Run the narrowest relevant validation available. Report tests or checks that
  were not run and why.

## Documentation

- Prefer clear code over comments that repeat it.
- Update docs when a change affects public APIs, configuration, developer
  workflows, deployment, or user-visible behavior. Keep them concise and do not
  duplicate content.

## Ordering

- Insert new entries into hand-maintained unordered lists in alphabetical
  position. Do not reorder existing entries, and preserve order that carries
  meaning (precedence, dependency, registration, initialization).
- Where a formatter, linter, or generator owns sorting, use it instead of
  sorting manually.
