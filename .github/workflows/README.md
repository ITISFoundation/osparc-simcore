# GitHub Actions workflows

Workflow file names answer *what does this do when it fires?*, not just *what
event triggers it?*:

- `ci-*` — continuous integration: builds and/or tests a change and gates it
  (push, pull request, merge queue). Shown as a pass/fail check on a commit.
- `cd-*` — continuous delivery/deployment: triggered by release tags, builds
  final images and publishes/deploys them. Treat as production-touching.
- `chore-*` — repository housekeeping or automation (labeling, cache cleanup,
  lockfile repair). Rides on events like `pull_request` but is not a merge gate.
- `_-*` — reusable workflow library (`workflow_call` only); never runs
  standalone and produces no checks.
- no prefix — scope-named checks or scheduled scans that state the subsystem
  they guard (e.g. `client-eslint`, `codspeed`, `codeql-analysis`).

Rules:

- File name is kebab-case `<prefix>-<scope>[-<qualifier>].yml`; the displayed
  `name:` is the same words in Title Case, unquoted, so a failing check maps
  1:1 back to its file.
- Encode the trigger in the name only when it distinguishes siblings
  (e.g. `cd-staging` vs `cd-release`).
- Do not reuse a generic display name such as `CI`; exactly one workflow may
  own it, and status badges/branch protection reference it by string.
- A workflow that triggers on `pull_request_target` needs an Actions event
  policy that explicitly allows the event, and a policy matches workflows by
  file path. Do not rename or move such a workflow without updating the
  policy, or its runs stop. The workflows that rely on it say so at the top of
  the file: <https://gh.io/securely-using-pull_request_target>.
- Third-party actions are pinned to a full commit SHA, with the release it
  resolves to kept in a trailing comment, e.g.
  `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.
  Never use a floating tag (`@v7`, or a tag alone). Dependabot owns the
  `github-actions` ecosystem in `.github/dependabot.yml` and bumps the SHA and
  its comment together, so do not hand-edit a pin to a newer version. Local
  actions (`uses: ./.github/actions/...`) are already pinned by path.
