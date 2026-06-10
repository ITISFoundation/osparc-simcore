---
applyTo: '.github/prompts/**/*.prompt.md'
description: 'Naming conventions for agent prompts: lowercase kebab-case with optional prefixes for grouping.'
---

# Prompt naming conventions

## Hard rules

- **Filename pattern: `{prefix-}{action}.prompt.md`** (e.g. `ref-aiohttp-appkey.prompt.md`)
- **Lowercase kebab-case only** (`[a-z0-9-]`, 1–64 chars before `.prompt.md`)
- **Action-oriented** — reads as the task it performs

## Prefixes (optional)

Use a single prefix to group related prompts by primary purpose:

| Prefix  | Purpose |
|---------|---------|
| `chore` | Maintenance, deps, config |
| `docs`  | Documentation, user messages |
| `ref`   | Refactoring, code restructuring |
| `lint`  | Linting, formatting, conventions |
| `test`  | Testing |

Examples: `ref-aiohttp-appkey.prompt.md`, `lint-pre-commit-hooks.prompt.md`, `docs-user-messages.prompt.md`.

Domain-specific prompts without prefix are acceptable (e.g. `fix-something.prompt.md`).

IMPORTANT: AUTO-EXTEND prefixes table above if a prompt cannot be grouped in the list.
