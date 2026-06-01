---
description: "Create or update a skill's metadata.json routing index inside the references/ folder"
name: "Create Skill metadata.json"
argument-hint: "Point me at the skill folder (SKILL.md + references/) to index"
agent: "agent"
model: Claude Haiku 4.5 (copilot)
---
You are helping a developer create or update a `metadata.json` file for an agent skill.

This file lives **inside the `references/` folder** alongside `SKILL.md` (at the same skill level). Its purpose is:
- Act as a routing index so an agent knows what exists and when to load it, without reading everything upfront
- Record authoring intent and token-budget decisions so the skill can be maintained coherently
- Provide a strategies catalog mapping testing/implementation patterns to headers, reference docs, and examples
- Track changes via a changelog

---

## Step 1 — Detect mode

Check whether a `metadata.json` already exists in `references/metadata.json`.

- If **yes**: you are in **UPDATE** mode. Parse it, identify what has changed based on any new context (updated SKILL.md, new references, new strategies, etc.), and produce a revised file. Append a changelog entry.
- If **no**: you are in **CREATE** mode. Produce a new file from scratch. Ask only for what is strictly missing and cannot be inferred.

---

## Step 2 — Gather required information

From the provided context (`SKILL.md`, reference files, testsuite examples, CI config, etc.) infer as much as possible. For anything that cannot be inferred, ask the developer directly. Keep questions grouped and minimal.

Required fields:
- `name` — skill directory name
- `scope` — what codebase(s) and projects this covers
- `optimized_for_model` — target model (ask if not stated)
- `last_updated` — today's date
- `strategies_catalog.entries` — one entry per distinct pattern the skill teaches (see schema below)

For each strategy entry, extract from context:
- `id` — short kebab-case identifier
- `applies_to` — one sentence: what class/pattern/situation this covers
- `helper` — the key class or function the developer uses
- `header` — relative path to the defining header
- `reference` — path to the relevant reference doc section (e.g. `references/foo.md#anchor`)
- `example` — one representative file path (or array if multiple)

If any of these cannot be inferred and are not provided, ask. Do not invent paths or class names.

---

## Step 3 — Authoring guidelines

Populate `authoring_guidelines` only if:
- Sources are explicitly provided, or
- The SKILL.md contains clear structural decisions that can be attributed

If none are available, omit the field entirely. Do not fabricate URLs.

---

## Step 4 — Output

Produce the final `metadata.json` directly. No preamble, no explanation.

Rules:
- **File location**: `references/metadata.json` (inside the `references/` folder, not at skill root)
- All string values must be concise (one sentence max for descriptions)
- `changelog` entries: one line, factual, what changed and why
- `strategies_catalog.purpose` must state the extensibility contract clearly
- Do not include fields that are empty or unknown
- Schema version: `https://json-schema.org/draft/2020-12/schema`
- Add `"maintained_via"` with a one-line instruction on how to keep the file in sync

---

## Clarification behavior

If context is ambiguous or incomplete, ask targeted questions before proceeding. Group them. Do not ask about things that can be reasonably inferred. Do not ask for confirmation on output — just produce it.
