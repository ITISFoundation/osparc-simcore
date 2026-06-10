---
applyTo: '.github/skills/**/SKILL.md'
description: 'Naming conventions for agent skills: lowercase kebab-case with optional prefixes for grouping.'
---

# Skill naming conventions

## Hard rules

- **Folder name == `name` frontmatter** (mismatch causes silent discovery failures)
- **Lowercase kebab-case only** (`[a-z0-9-]`, 1–64 chars)
- **Action-oriented** — reads as the task it performs

## Prefixes (optional)

Use a single prefix to group related skills by primary purpose:

| Prefix  | Purpose |
|---------|---------|
| `chore` | Maintenance, deps, config |
| `test`  | Testing, CI |
| `rev`   | PR review, code feedback |
| `debug` | Debugging, diagnostics |

Examples: `chore-propagate-security-fix`, `chore-prune-pydeps`, `review-my-changes`.

No prefix is fine if the skill is domain-specific (e.g. `healthcheck`, `postgres-migration`, `grafana-query`).
