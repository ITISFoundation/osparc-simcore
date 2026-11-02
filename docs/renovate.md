# Dependency updates (Renovate)

A self-hosted Renovate updates the dependencies in this repository: Python
lockfiles, Docker images, GitHub Actions, `uv`, and the Python patch version.
Neither the Mend-hosted app nor Dependabot opens them. Dependabot alerts stay on
as a vulnerability source only.

| What | Where |
| --- | --- |
| Runner (nightly + on demand) | [.github/workflows/chore-renovate.yml](../.github/workflows/chore-renovate.yml) |
| Repository configuration | [.renovaterc.jsonc](../.renovaterc.jsonc) |
| Admin configuration (`allowedCommands`, `platformCommit`) | [.github/renovate/global-config.json5](../.github/renovate/global-config.json5) |
| Lockfile re-resolution post-upgrade task | [.github/renovate/resync_lockfiles.py](../.github/renovate/resync_lockfiles.py) |
| Milestone assignment for new pull requests | [.github/workflows/chore-renovate-milestone.yml](../.github/workflows/chore-renovate-milestone.yml) |
| Review gate (drafts, review requests, automerge marking) | [.github/workflows/chore-renovate-review-gate.yml](../.github/workflows/chore-renovate-review-gate.yml) |
| Who reviews them | [CODEOWNERS](../.github/CODEOWNERS), last block |
| Who merges them | [mergify.yml](../.github/mergify.yml) |

Renovate runs as the GitHub App `osparc-simcore-renovate[bot]`. That App signs
its commits and runs `make reqs` as a post-upgrade task, which the hosted
Renovate cannot do. Do not push a fixup commit under another author. CI waits
for approval before running a commit it did not sign, and Renovate stops
touching a branch that someone else wrote last.

## Update policies

- **Security fixes skip the throttling.** `osvVulnerabilityAlerts` and the
  Dependabot alerts open the pull request on the next run. It needs no
  Dependency Dashboard approval and waits for no cool-down. It gets the
  `security` label and `🤖-automerge`, so a security fix whose checks pass
  merges through the fast lane (see below) whatever the version jump.
  `vulnerabilityFixStrategy: "highest"` makes it propose the
  newest release, not the lowest one that fixes the vulnerability. A branch then
  cannot offer two versions of the same package.
- **Regular updates are throttled.** Two new pull requests per run, two open at
  a time. The Dependency Dashboard holds the rest. It is also where you tick
  Docker image majors and the monthly `lockFileMaintenance` runs; majors of
  Python packages, GitHub Actions and `uv` arrive as regular pull requests.
- **Cool-downs.** 14 days for every dependency: pip-compile lockfiles, GitHub
  Actions, and `uv`. Security fixes skip them.
- **One PR per dependency.** A pip-compile package gets a single PR that moves
  its pin in every `requirements/` directory at once (the resync post-upgrade
  task propagates it). No PRs grouped per directory or per area. The
  `opentelemetry-*` packages are the exception: they ship in two coordinated
  release trains that pin each other, so one PR moves the whole family
  (`renovate/opentelemetry`, majors on their own branch). Security pull
  requests are never grouped: Renovate's `vulnerabilityAlerts` default resets
  the group name, so a vulnerable package gets its own immediate PR.

## From pull request to merge

Renovate never merges. `automerge` stays `false`. Mergify merges its pull
requests, either reviewed or through a fast lane, and reviewers are requested
only after the checks have finished:

1. Renovate opens every pull request as a draft (`draftPR`), so GitHub does not
   auto-request the code owners up front — security pull requests included.
2. `chore-renovate-review-gate.yml` polls the drafts every 15 minutes. Once all
   checks of the head commit are done:
   - **all passed, `🤖-automerge` label** (patch, pin and digest bumps, and every
     security fix): the pull request is marked ready silently and the
     `renovate-fast` Mergify queue merges it without any review;
   - **all passed, no label** (minors, majors, everything else): marked ready and
     the four code owners are requested — this is when a review is wanted;
   - **failing**: nothing for 3 h so Renovate can push its own fix. If the last
     commit is still failing, the pull request is marked ready, labeled
     `🤖-ci-failing`, the owners are requested and a comment lists the failing
     checks. Remove the label to have the workflow ask again when the state
     changes.
3. The reviewed path merges once Mergify's conditions match: the branch is
   rebased on `master` (the ruleset marks the checks *strict*), reviewers
   approve twice, request no changes, leave no thread open, and a code owner
   approves. For the files Renovate writes, the owners are the four people in
   the last block of `.github/CODEOWNERS`. They own *only* version manifests:
   `**/requirements/**`, Dockerfiles, `docker-compose*.yml`, `.python-version`,
   and the Actions pinned under `.github/workflows/**`. One dependency bump
   rewrites dozens of directories at once, so leaving those files to the
   per-service rules would make every security fix wait on six or seven
   reviewers.

Add the `🤖-do-not-merge` label to hold a pull request back, from either lane.
Remove it to let the pull request go. On the reviewed path, anyone else may
still approve, and their review counts toward the two approvals, but it does not
clear the code-owner gate.

The fast lane needs two one-time settings, both outside this repository:

- GitHub enforces a ruleset's requirements on the actor that performs the
  merge, not on the pull request author. The fast-lane pull requests never
  collect the two approvals and the code-owner review, so *Mergify* — the app
  that presses the merge button — must be exempt from exactly those
  requirements: the "Require a pull request before merging" rule lives in its
  own *master-branch-reviews* ruleset with the Mergify App on the bypass list
  in *exempt* mode and Maintain in *pull request* mode, which is what
  Mergify's own setup docs prescribe
  (<https://docs.mergify.com/merge-queue/setup>). Required status checks and the
  push protections stay in the *master branch* ruleset with no Mergify entry, so
  GitHub itself still refuses Mergify a merge with failing checks. Human pull
  requests lose nothing: the requirements are unchanged, and Mergify keeps
  demanding the approvals for everything the fast lane does not claim;
- the `🤖-automerge` label means "fast-lane material" and Renovate applies it.
  It used to be a hand-typed queue hint and is still on some older human pull
  requests, where it does nothing: the catch-all Mergify rule excludes the
  label, so remove it there.

When the resync task cannot propagate a pin to every directory that constrains
it, it leaves `renovate-resync-report.md` in the pull request and Renovate
reports a failing `renovate/artifacts` check. A patch-level resync failure
therefore keeps the pull request out of the fast lane: the review gate workflow
requests the code owners after the 3 h cool-down.

## Adding something new for Renovate to manage

Add it to the last block of `.github/CODEOWNERS` too, whether it is a new
lockfile directory or a new file that holds a version pin. Otherwise GitHub asks
the owners of every service the pull request touches, or nobody at all, and the
pull request stalls.
