# Dependency updates (Renovate)

All dependencies — Python lockfiles, Docker images, GitHub Actions, `uv` and the
Python patch version — are updated by a **self-hosted Renovate**, not by the
Mend-hosted app or Dependabot. Dependabot alerts stay enabled as a vulnerability
source only.

| What | Where |
| --- | --- |
| Runner (nightly + on demand) | [.github/workflows/chore-renovate.yml](../.github/workflows/chore-renovate.yml) |
| Repository configuration | [.renovaterc.jsonc](../.renovaterc.jsonc) |
| Admin configuration (`allowedCommands`, `platformCommit`) | [.github/renovate/global-config.json5](../.github/renovate/global-config.json5) |
| Lockfile re-resolution post-upgrade task | [.github/renovate/resync_lockfiles.py](../.github/renovate/resync_lockfiles.py) |
| Milestone assignment for new PRs | [.github/workflows/chore-renovate-milestone.yml](../.github/workflows/chore-renovate-milestone.yml) |
| Who reviews the PRs | [CODEOWNERS](../.github/CODEOWNERS), last block |
| Who merges them | [mergify.yml](../.github/mergify.yml) |

It runs as the GitHub App `osparc-simcore-renovate[bot]`, so its commits are signed
by the App and it may run `make reqs` as a post-upgrade task — something the hosted
Renovate cannot do. That is also why a fixup commit by another author is worse than
useless here: CI waits for approval on foreign commits, and Renovate stops touching
a branch it did not write last.

## Update policies worth knowing

- **Security fixes land immediately.** `osvVulnerabilityAlerts` plus the GitHub
  Dependabot alerts create the PR on the next run, without Dependency Dashboard
  approval and without waiting for the cool-downs below. The PR gets the `security`
  label and proposes the newest release rather than the lowest fixed one
  (`vulnerabilityFixStrategy: "highest"`), so one branch never offers two different
  versions for the lockfiles on either side of the fix.
- **Regular updates are throttled**: 2 new PRs per run, 2 open at a time. Anything
  else waits on the Dependency Dashboard, which is also where majors and the monthly
  `lockFileMaintenance` runs have to be ticked.
- **Cool-downs**: 7 days for GitHub Actions and `uv`, 3 days for `packages/**`
  dependencies, 14 days for `services/**`. Security fixes skip them.

## From PR to merge

Renovate never merges (`automerge: false`). It labels its PRs `🤖-automerge` and
Mergify queues them, like any other PR, once:

1. the required status checks are green and, since they are *strict*, rebased on
   `master`;
2. two approving reviews are in, none changes requested, no thread unresolved;
3. a code owner has approved. For the files Renovate writes, those are the four
   people in the last block of `.github/CODEOWNERS`. They own *only* version
   manifests (`**/requirements/**`, Dockerfiles, `docker-compose*.yml`,
   `.python-version` and the Actions pinned under `.github/workflows/**`): one
   dependency bump rewrites dozens of directories at once, and leaving those
   files to the per-service rules would make every security fix wait on six or
   seven reviewers.

To hold a PR back, add the `🤖-do-not-merge` label; remove it to let it go again.
Reviewers outside the owner set are still welcome — they just cannot satisfy the
code-owner gate.

When the resync task cannot propagate a pin to every directory that constrains it,
it leaves `renovate-resync-report.md` in the PR and Renovate reports a failing
`renovate/artifacts` check. Neither is a required check, so read them before
approving.

## Adding something new for Renovate to manage

Anything new it should rewrite (a new lockfile directory, a new file holding a
version pin) has to be inside the last block of `.github/CODEOWNERS` too. Otherwise
the PR that updates it gets requested reviewers spread over the services it touches,
or none at all, and stalls.
