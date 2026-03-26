---
name: cross-service-issue-check
description: 'Investigate whether an issue in one service also exists in other services under services/. Use when a bug, regression or repeated implementation pattern may be shared by sibling services. Checks implementations, tests, and behavior differences, then reports affected and unaffected services.'
argument-hint: 'Describe the issue or code pattern that might exist in other services'
---

# Cross-Service Issue Check

## When to Use

- A user asks whether the same bug also exists in other services
- A failure appears tied to a shared dependency such as RabbitMQ, Redis, Postgres, or a shared service library
- A healthcheck, API route, middleware, client wrapper, or background task pattern looks copy-pasted across services
- A fix in one service might need equivalent changes elsewhere
- Tests in one service suggest a behavior that may have been replicated in sibling services

## Goal

Determine whether the issue is isolated or repeated across services, and make the answer concrete by identifying:

- affected services
- unaffected services or known exceptions
- include only services that actually apply the same pattern that can cause the issue
- current behavior differences
- existing test coverage and gaps

## Procedure

1. Define the issue signature.
   Extract the most searchable identifiers from the original issue: error messages, constant names, route names, dependency names, exception classes, helper functions, or key conditionals.

2. Search across services.
   Search under services/ for the signature using shared constants, function names, route handlers, and exception types. Prefer finding behaviorally similar code over string-only matches.

3. Compare behavior, not just code presence.
   For each candidate service, trace the path from the failing dependency or condition to the external outcome.

4. Check tests.
   Inspect service tests to see whether they verify the behavior as an HTTP response or merely expect an internal exception to be raised. Treat tests as evidence of intended current behavior.

5. Classify the result.
   Group services into:
   - same issue confirmed
   - same pattern but safely handled
   - insufficient evidence
   - not applicable

6. Report concrete evidence.
   Include the specific service files and tests that support the classification. Keep the summary short, but make the evidence auditable.

7. If code changes are requested, apply the fix consistently.
   When the user wants remediation, update all confirmed services that should share the fix, unless there is a documented reason to keep behavior different.

## Output Format

Provide:

- a short conclusion
- affected services
- evidence from implementation files
- evidence from test files
- recommended next step only if action is warranted
