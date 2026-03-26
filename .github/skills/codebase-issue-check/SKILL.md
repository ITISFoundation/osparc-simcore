---
name: codebase-issue-check
description: 'Investigate whether the issue described by the user is present in any other place in the repository. Use when a bug, regression or repeated implementation pattern may be shared. Checks implementations, tests, and behavior differences, then reports affected and unaffected areas.'
argument-hint: '(use Claude Opus 4.6 for better results) describe the issue or code pattern that might exist elsewhere'
---

# Codebase Issue Check

## When to Use

- A user asks whether the same bug also exists in other places in the codebase
- A failure appears tied to a similar used pattern
- A code block with similar structure using the same feature might have a similar issue
- A fix in one place might need equivalent changes elsewhere
- Tests suggest a behavior that may have been replicated in other places

## Goal

Determine whether the issue is isolated or repeated, and make the answer concrete by identifying:

- affected areas
- unaffected areas or known exceptions
- include only areas that actually apply the same pattern that can cause the issue
- current behavior differences
- existing test coverage and gaps

## Procedure

1. Define the issue signature.
   Extract the most searchable identifiers from the original issue: error messages, constant names, route names, dependency names, exception classes, helper functions, or key conditionals.

2. Search across the codebase.
   Search under the relevant directories for the signature using shared constants, function names, route handlers, and exception types. Prefer finding behaviorally similar code over string-only matches.

3. Compare behavior, not just code presence.
   For each candidate area, trace the path from the failing dependency or condition to the external outcome.

4. Check tests.
   Inspect tests to see whether they verify the behavior. Treat tests as evidence of intended current behavior.

5. Classify the result.
   Group areas into:
   - same issue confirmed
   - same pattern but safely handled
   - insufficient evidence
   - not applicable

6. Report concrete evidence.
   Include the specific files and tests that support the classification. Keep the summary short, but make the evidence auditable.

7. If code changes are requested, apply the fix consistently.
   When the user wants remediation, update all confirmed areas that should share the fix, unless there is a documented reason to keep behavior different.

## Output Format

Provide:

- a short conclusion
- affected areas
- evidence from implementation files
- evidence from test files
- recommended next step only if action is warranted
