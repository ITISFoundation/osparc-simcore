---
name: write-pull-request
description: >-
  Write and create a pull request for this repository: gitmoji title, the
  PULL_REQUEST_TEMPLATE.md sections, the compactness rules, and the gh
  commands. Use when: create a PR, open a pull request, draft a PR, write or
  update the PR description, description of these changes, ready to merge,
  hand over a Renovate pull request.
---

# Write Pull Request

## When to Use

- A branch is finished and needs a pull request
- An existing description needs rewriting
- A Renovate pull request is taken over

## Before writing

- Read [PULL_REQUEST_TEMPLATE.md](../../PULL_REQUEST_TEMPLATE.md). Its section
  names are fixed, and the comment at the top lists the accepted gitmoji.
- Collect the facts from the branch: `git --no-pager log master..HEAD`, the
  diff, and any measurement a bullet will quote. Verify a number before writing
  it, or write `not measured yet`.

## Title

One gitmoji from the template legend followed by what changed, for example
`📝 docs: align grafana-query skill with the Victoria monitoring stack`.

## Description

- Follow the template structure. Fill every section. Where one does not apply,
  write `n/a`.
- Open with `## Goal`: one sentence on why the pull request exists.
- State the final solution, the facts and the measurements. No trial or process
  narrative, no step-by-step history of how the branch evolved.
- `## What do these changes do?`: the change in behavior, not the diff. Name a
  file only when that file is itself the subject (a generated spec, a lockfile,
  a config a reviewer must open); name a workflow by its display name, never its
  file name. Say nothing about code the pull request does not touch.
- At most two sentences per bullet. State each fact once: a mechanism explained
  in one bullet must not come back in the next.
- Work outside the `## Goal` sentence goes under a `### Bonus` sub-title, not
  mixed into the main bullets. Better still, put it in its own pull request.
- Background a reviewer needs but did not ask for goes under a `### Context`
  sub-title: two sentences, facts or measurements only.
- `## How to test`: commands and snippets a reviewer runs, or `n/a`. What you
  ran while developing does not belong here, and nowhere else either.
- Work to do after merge goes under a `### Follow-up` sub-title, not in
  `## How to test`.
- `## Dev-ops`: the work that still has to be done at deploy time, or `n/a`.
  Steps already carried out belong nowhere in the description. See
  [docs/devops-checklist.md](../../../docs/devops-checklist.md).
- Do not report tooling that runs by default. Pre-commit, linting and the test
  suite passing is expected. Report only what a reviewer cannot infer:
  measurements, and what was deliberately left untested.
- Use the platform's own words: checks pass or fail, reviewers are requested. No
  `green` or `red`, no `paging the owners`, no metaphors such as `once CI has
  spoken`. Literal wording only.
- Keep the caveats. Do not dress a known limitation in optimistic prose, and do
  not claim more than the measurements support.
- Performance pull requests: before and after measurements (CI step durations,
  baseline mean against new value). If a measurement is not available yet, leave
  an explicit placeholder and fill it in once the checks complete.

## Unslop before posting

Run the draft through [unslop](../unslop/SKILL.md), whoever wrote it, so the
description carries only what changed and why. That skill lists what counts as
slop and what to cut.

## AI assistance

Tick `🤖 This PR was AI generated` when it was, then name each contributing tool
on its own line, as the template describes:

```text
Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]
```

## Creating the pull request

Push only to create the pull request. Otherwise the general conventions say
commit locally and stop. Draft unless told otherwise; if intent is unclear, ask.

```bash
git push -u origin <branch>
gh pr create --draft \
  --repo ITISFoundation/osparc-simcore --base master \
  --head <fork-owner>:<branch> \
  --title "<gitmoji> <summary>" --body-file <file>
```

The base branch is `master`. To change the title or body afterwards, `gh pr
edit` fails with a GraphQL scope error when the token lacks `read:org`. Patch
through the REST endpoint instead:

```bash
gh api -X PATCH "repos/ITISFoundation/osparc-simcore/pulls/<number>" \
  -f title="<title>" -F body=@<file>
```

## Renovate handover

A pull request taking over a Renovate one fills the same template. Renovate's
release notes stay in its pull request, linked from `## Related issue/s` as
`replaces #<number> (Renovate's release notes are there)`, and the title keeps
Renovate's with `(taken over from #<number>)` appended. Never push to
`renovate/*` branches. The handover steps are in
[docs/renovate.md](../../../docs/renovate.md#fixing-a-failing-renovate-pull-request).
