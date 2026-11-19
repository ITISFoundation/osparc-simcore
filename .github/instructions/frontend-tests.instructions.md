---
description: "Use when writing or reviewing Node.js tests for the Qooxdoo client. Covers test titles, assertions, and regression cases."
applyTo: "services/static-webserver/client/tests/**/*.test.cjs"
---

# Qooxdoo client tests

- Use `node:test` and `node:assert/strict`. Name test files `<feature>.test.cjs`.
- Write titles as `<feature> <observable outcome> when <condition>`.
- Example: `Activity Center shows Cancel when an executing run is translated`.
- Give parameterized cases distinct names without stringifying objects.
- Exercise production behavior and stub only its dependencies.
- Assert calls to stubbed renderers, not HTML supplied by the stub.
- Use a browser test for real DOM or user interaction assertions.
- Cover both shown and hidden states when testing visibility.
- Verify regression tests fail without the fix.
- Every test must fail if the implementation returns a wrong value.
