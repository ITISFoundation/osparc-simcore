---
name: write-pull-request
description: >-
  Create or update a pull request in this repository. Use when: create a PR,
  open a pull request, draft a PR, update a pull request, edit or rewrite the
  PR description, change the PR title, pick pull-request work up on another
  machine, continue an existing pull request, hand over a Renovate pull
  request, or any request to prepare a pull request.
---

# Write Pull Request

## When to Use

Any time the user asks, whatever the state of the branch:

- Creating a pull request
- Updating an existing one: description, title, or pushing new commits to it
- Picking pull-request work up again, for example after switching computers
- Taking over a Renovate pull request

## Topology

A pull request goes from a branch in your fork to the `master` branch of the
upstream repository, `ITISFoundation/osparc-simcore`. The fork branch is always
the head and never the base.

This repository's remotes are usually `origin` for the fork and `upstream` for
`ITISFoundation/osparc-simcore`, with `upstream` configured so pushes to it
fail. Check with `git remote -v` before pushing. After a machine switch,
`gh pr view --json baseRefName,headRefName,isDraft,files` reports what the pull
request currently is.

## Where each rule lives

[PULL_REQUEST_TEMPLATE.md](../../PULL_REQUEST_TEMPLATE.md) is the authority on
the section list, the gitmoji legend for the title, and the `Assisted-by:`
format. [unslop](../unslop/SKILL.md) is the authority on prose quality and what
to cut. Neither is restated here. The template is also the file a reviewer
opens first, so read it before writing rather than working from memory.

## Facts before prose

Take the content from the branch, not from the conversation: the commit list
from `git --no-pager log master..HEAD`, the diff, and every measurement a bullet
quotes. Verify a number before writing it, or write `not measured yet`.

## Rules the template does not carry

- Fill every section. Where one does not apply, write `n/a`.
- State each fact once. A mechanism explained in one bullet must not come back
  in the next.
- No process narrative. State the final solution, the facts, the measurements.
- Do not report tooling that runs by default. Pre-commit, linting and the test
  suite passing is expected. Report only what a reviewer cannot infer:
  measurements, and what was deliberately left untested.
- Use the platform's own words: checks pass or fail, reviewers are requested. No
  `green` or `red`, no metaphors such as `once CI has spoken`.
- Keep the caveats. Do not claim more than the measurements support. A
  performance pull request gives before and after numbers.

## Line width

Do not wrap a pull request body. GitHub renders the markdown and wraps it for
the reader, so one bullet stays on one line however long it runs. The 80-column
limit this repository's markdown linter enforces applies to tracked files, not
to a pull request.

## Unslop before posting

Run the draft through [unslop](../unslop/SKILL.md), whoever wrote it, so the
description carries only what changed and why.

## Creating and updating

Draft unless told otherwise; if intent is unclear, ask. The flags below encode
the topology above.

```bash
git push -u origin <branch>
gh pr create --draft --repo ITISFoundation/osparc-simcore --base master \
  --head <fork-owner>:<branch> --title "<gitmoji> <summary>" \
  --body-file <file>
```

To change title or body afterwards, `gh pr edit` aborts with a GraphQL scope
error when the token lacks `read:org`: its read query asks for
organization-backed fields the edit itself does not need. The REST endpoint
accepts the same patch with a `repo`-only token:

```bash
gh api -X PATCH "repos/ITISFoundation/osparc-simcore/pulls/<number>" \
  -f title="<title>" -F body=@<file>
```

## Renovate handover

A pull request taking over a Renovate one fills the same template. Renovate's
release notes stay in its pull request, linked from `## Related issue/s` as
`replaces #<number> (Renovate's release notes are there)`, and the title keeps
Renovate's with `(taken over from #<number>)` appended. Never push to
`renovate/*` branches. The steps are in
[docs/renovate.md](../../../docs/renovate.md#fixing-a-failing-renovate-pull-request).
