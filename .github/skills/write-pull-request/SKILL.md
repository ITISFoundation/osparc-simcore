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

On request, at any point in the life of a branch, including before the work is
finished and after a machine switch.

## Before writing

Read [PULL_REQUEST_TEMPLATE.md](../../PULL_REQUEST_TEMPLATE.md). It owns the
section list, the gitmoji legend for the title and the `Assisted-by:` format.

Take the content from the branch rather than the conversation: the commit list
from `git --no-pager log master..HEAD`, the diff, and every measurement a bullet
quotes. Verify a number before writing it, or write `not measured yet`.

## Layout

A pull request goes from a branch in your fork to the `master` branch of the
upstream repository, `ITISFoundation/osparc-simcore`. The fork branch is the
head, never the base.

The remotes are normally `origin` for the fork and `upstream` for
`ITISFoundation/osparc-simcore`, with `upstream` configured so pushes to it
fail. Check with `git remote -v`. To recover the state of an existing pull
request, `gh pr view --json baseRefName,headRefName,isDraft,files`.

## Description rules

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
- Do not wrap the body: GitHub wraps it for the reader. The 80-column limit the
  repository's markdown linter enforces applies to tracked files, not to a pull
  request.
- Run the draft through [unslop](../unslop/SKILL.md) before posting, whoever
  wrote it.

## Creating

Draft unless told otherwise. If intent is unclear, ask.

```bash
git push -u origin <branch>
gh pr create --draft --repo ITISFoundation/osparc-simcore --base master \
  --head <fork-owner>:<branch> --title "<gitmoji> <summary>" \
  --body-file <file>
```

## Updating

To change title or body, `gh pr edit` aborts with a GraphQL scope error when the
token lacks `read:org` because its read query asks for organization-backed
fields. The REST endpoint accepts the same patch with a `repo`-only token:

```bash
gh api -X PATCH "repos/ITISFoundation/osparc-simcore/pulls/<number>" \
  -f title="<title>" -F body=@<file>
```

## Renovate handover

Fill the same template. Renovate's release notes stay in its pull request,
linked from `## Related issue/s` as
`replaces #<number> (Renovate's release notes are there)`. The title keeps
Renovate's with `(taken over from #<number>)` appended. Never push to
`renovate/*` branches. The steps are in
[docs/renovate.md](../../../docs/renovate.md#fixing-a-failing-renovate-pull-request).
