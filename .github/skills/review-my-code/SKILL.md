---
name: review-my-code
description: 'Perform an initial pull request review on the current branch. Use when: reviewing a PR, code review, checking branch changes before merge, verifying coding standards compliance, finding security issues, reviewing software design decisions, pre-merge review.'
---

# Pull Request Review

Performs a structured code review of the current branch against `master`. The review checks for coding standards violations, software design issues, and security flaws.

## When to Use

- Before opening a pull request
- To self-review changes on your feature branch
- To verify compliance with repository coding conventions

## Procedure

Follow these phases **strictly and in order**. Do not skip phases or combine them.

---

### Phase 1: Gather Context

1. **Identify the current branch**:
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   Confirm you are NOT on `master`. If on `master`, stop and tell the user.

2. **Generate the full diff against master**:
   ```bash
   git diff master...HEAD
   ```
   Read the **entire** diff output. If the diff is very large, process it in chunks, but ensure every changed file is reviewed.

3. **List all changed files by type**:
   ```bash
   git diff master...HEAD --name-only --diff-filter=ACMR
   ```
   This gives the list of added, copied, modified, and renamed files.

4. **Load the applicable instruction files**. Read the following instruction files from the repository — they define the team's coding standards:
   - `.github/instructions/general.instructions.md` — always
   - `.github/instructions/python.instructions.md` — if any `*.py` files changed
   - `.github/instructions/python-tests.instructions.md` — if any `test*.py` or `conftest.py` files changed
   - `.github/instructions/node.instructions.md` — if any `*.js` files changed
   - `.github/instructions/web-server-openapi.instructions.md` — if any `api/specs/web-server/**` files changed

---

### Phase 2: Analysis

Analyze every changed file in the diff. For each file, perform **all five** of the following checks:

#### Check 1 — Coding Standards Compliance

Compare every change against the loaded instruction files. Flag violations of:
- Type annotation rules (missing annotations, wrong style)
- Import conventions (relative vs absolute, placement)
- Python version syntax (PEP 695 type aliases, `X | None` unions, generic class syntax)
- Pydantic API usage (v1 patterns like `.dict()`, `.json()`, `parse_obj()`, `class Config`)
- SQLAlchemy patterns (JOIN+GROUP BY where EXISTS is preferred, anti-join via LEFT JOIN instead of NOT EXISTS)
- Error handling patterns (missing `OsparcErrorMixin`, raw string errors instead of `user_message()`)
- Test conventions (class-based grouping, missing `# nosec`/`# noqa` where needed, `autouse=True` in conftest, generic test file names)
- Controller-Service-Repository layering violations (business logic in controllers, direct repository calls from controllers)
- JSON serialization (using `json.dumps`/`json.loads` instead of `common_library.json_serialization`)
- Logging (f-strings in log messages instead of `%s` formatting)
- FastAPI lifecycle (deprecated `add_event_handler` instead of lifespan)
- Module exports (`__all__` format)

#### Check 2 — Software Design

Evaluate the architectural quality of the changes:
- **Layering violations**: Does the change respect Controller-Service-Repository boundaries?
- **Unnecessary complexity**: Can any abstraction, helper, or indirection be simplified?
- **Code duplication**: Is logic repeated that should be extracted?
- **API surface**: Are new public functions/classes necessary, or do they leak internals?
- **Naming**: Are names descriptive and consistent with existing conventions?
- **Coupling**: Does the change introduce tight coupling between modules that should be independent?
- **Maintenance hazards**: Will this code be hard to modify, test, or debug in the future?

#### Check 3 — Security

Scan for common vulnerabilities (OWASP Top 10 and Python-specific):
- SQL injection (raw string interpolation in queries)
- Unsanitized user input reaching DB queries, file paths, or shell commands
- Hardcoded secrets, tokens, or credentials
- Insecure deserialization (`pickle.loads` without `# noqa: S301`, `yaml.load` without `SafeLoader`)
- Path traversal (user-controlled paths without validation)
- Missing authentication or authorization checks on new endpoints
- Overly broad exception handling that silences security-relevant errors
- Use of `eval()`, `exec()`, or `__import__()` with user input
- Debug code left in (e.g., `print()` without `# noqa: T201`, commented-out security checks)

#### Check 4 — Test Coverage of Critical Code

Identify critical or complex code paths in the changes and verify they have adequate test coverage:
- **New business logic** — Are service-layer functions covered by unit tests?
- **Edge cases** — Do tests cover error paths, boundary conditions, and empty/null inputs?
- **New endpoints** — Are there integration tests for new or modified API routes?
- **Complex conditionals** — Are branching paths exercised by different test cases?
- **Data transformations** — Are serialization/deserialization and model conversions tested?

For any critical code path that lacks tests, suggest specific test cases the developer should add. Include concrete test function signatures and describe what each test should assert.

#### Check 5 — Snippet Verification

When you encounter small, self-contained logic (e.g., pure functions, data transformations, regex patterns, serialization round-trips) that can be verified in isolation, test it by running:
```bash
python -c "<snippet>"
```

This is useful for:
- Verifying regex patterns match expected inputs
- Checking serialization/deserialization round-trips
- Validating string formatting or template logic
- Confirming type coercion behaves as expected

**Environment requirement**: If the snippet requires project dependencies that are not available in the current Python environment, do **not** attempt to install them. Instead, ask the user to set up the environment with all dependencies installed, then retry.

---

### Phase 3: Report

After completing the full analysis, produce a **summary report** structured as follows:

```
## PR Review Summary

**Branch**: <branch-name>
**Files changed**: <count>
**Checks performed**: Coding Standards, Software Design, Security, Test Coverage, Snippet Verification

### Overview
<1-3 sentence summary of the overall quality of the changes>

### Findings

| # | Severity | Category | File | Description |
|---|----------|----------|------|-------------|
| 1 | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... |
```

**Severity levels**:
- **critical** — Must fix before merge (security flaw, data loss risk, broken functionality)
- **warning** — Should fix before merge (standards violation, design issue, maintenance hazard)
- **suggestion** — Nice to have (style improvement, minor simplification)

If no issues are found, say so explicitly: "No issues found. The changes look good to merge."

---

### Phase 4: Interactive Resolution

After presenting the summary table, process each finding **one at a time** in order of severity (critical first, then warning, then suggestion):

For each finding:
1. **Show the problematic code** — quote the exact lines from the diff
2. **Explain the problem** — why it violates the standard, poses a risk, or hurts maintainability
3. **Propose a concrete fix** — show the replacement code (not just a description)
4. **State the rationale** — why this specific fix is the right approach

Then **ask the user** whether to:
- **Accept** — apply the fix immediately
- **Decline** — skip this finding and move to the next
- **Discuss** — the user wants to provide context or ask for an alternative

Apply accepted fixes using file editing tools. After processing all findings, show a final summary of what was applied and what was skipped.

---

## Important Rules

- **Never skip the diff reading**. You must read the entire diff before reporting findings.
- **Be specific**. Always reference exact file paths and line numbers.
- **No false positives**. Only flag issues you are confident about. If unsure, frame it as a question to the user rather than a finding.
- **Respect existing patterns**. If the codebase uses a pattern consistently and the instructions don't prohibit it, don't flag it.
- **One finding at a time** in Phase 4. Do not batch multiple findings into a single prompt.
