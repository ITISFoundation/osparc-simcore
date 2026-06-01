---
applyTo: '.github/skills/**/SKILL.md'
description: 'Conventions for authoring agent skills in this repo: optional grouping prefixes and metadata.json usage. Complements the /create-skill meta-skill.'
---

# Skill authoring conventions

These conventions **complement** the `/create-skill` meta-skill (which handles the
mechanics of producing a `SKILL.md`). Use `/create-skill` to scaffold a skill, then
apply the conventions below for naming and metadata.

## 1. Naming

Hard rules:

- **Folder name == `name` frontmatter.** A mismatch causes silent discovery failures.
- **Lowercase kebab-case** only (`[a-z0-9-]`, 1–64 chars). No underscores, spaces, or capitals.
- **Action-oriented** name that reads as the task it performs.

### Grouping prefixes (recommended, not mandatory)

Prefix a skill name to group related skills and aid discovery. Use the prefix that
matches the skill's *primary* purpose:

| Prefix     | Use for |
|------------|------------------------------------------|
| `chore`    | Maintenance, deps, config |
| `docs`     | Written artifacts |
| `flow`     | Dev process automation |
| `lint`     | Convention enforcement |
| `test`     | Testing |
| `infra`    | CI/CD, pipelines, environments |
| `ref`      | Code restructuring |
| `rev`      | PR/MR analysis, feedback |
| `scaffold` | Boilerplate, templates |
| `dbg`      | Diagnosis, error triage |

Examples: `chore-prune-pydeps`, `chore-propagate-security-fix`.

Pick a single prefix — the one matching the dominant outcome. If a skill genuinely
fits none, a plain descriptive name (e.g. `healthcheck`, `postgres-migration`) is fine.

## 2. metadata.json (recommended)

Add a `references/metadata.json` routing index so the agent can discover what the
skill contains and when to load each reference without reading everything upfront.
This is especially valuable for multi-strategy or reference-heavy skills.

- Generate or update it with the `/create-skill-metadata` prompt
  ([.github/prompts/create-skill-metadata.prompt.md](../prompts/create-skill-metadata.prompt.md)).
- It always lives at `references/metadata.json` (inside the skill's `references/` folder).
- Keep its `name` field in sync with the skill folder name.

## 3. When renaming an existing skill

- Update the `name:` field in `SKILL.md` to match the new folder.
- Update the `name` field in `references/metadata.json`, if present.
- Grep the repo for the old skill path (`skills/<old-name>/`) and update all
  references (docs, workflows, scripts, `dependabot.yml`, etc.).
