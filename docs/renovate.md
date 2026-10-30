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
  `security` label. `vulnerabilityFixStrategy: "highest"` makes it propose the
  newest release, not the lowest one that fixes the vulnerability. A branch then
  cannot offer two versions of the same package.
- **Regular updates are throttled.** Two new pull requests per run, two open at
  a time. The Dependency Dashboard holds the rest. It is also where you tick
  majors and the monthly `lockFileMaintenance` runs.
- **Cool-downs.** 14 days for every dependency: pip-compile lockfiles, GitHub
  Actions, and `uv`. Security fixes skip them.
- **One PR per dependency.** A pip-compile package gets a single PR that moves
  its pin in every `requirements/` directory at once (the resync post-upgrade
  task propagates it). No PRs grouped per directory or per area.

## From pull request to merge

Renovate never merges. `automerge` stays `false`. Mergify queues its pull
requests like any other pull request once:

1. Mergify rebases the branch on `master` and the required status checks pass.
   The ruleset marks those checks *strict*, so an outdated branch cannot count;
2. reviewers approve twice, request no changes, and leave no review thread open;
3. a code owner approves. For the files Renovate writes, the owners are the four
   people in the last block of `.github/CODEOWNERS`. They own *only* version
   manifests: `**/requirements/**`, Dockerfiles, `docker-compose*.yml`,
   `.python-version`, and the Actions pinned under `.github/workflows/**`. One
   dependency bump rewrites dozens of directories at once, so leaving those
   files to the per-service rules would make every security fix wait on six or
   seven reviewers.

Add the `🤖-do-not-merge` label to hold a pull request back. Remove it to let the
pull request go. Anyone else may still approve, and their review counts toward
the two approvals, but it does not clear the code-owner gate.

When the resync task cannot propagate a pin to every directory that constrains
it, it leaves `renovate-resync-report.md` in the pull request and Renovate
reports a failing `renovate/artifacts` check. Neither of those checks is
required, so read both before you approve.

## Adding something new for Renovate to manage

Add it to the last block of `.github/CODEOWNERS` too, whether it is a new
lockfile directory or a new file that holds a version pin. Otherwise GitHub asks
the owners of every service the pull request touches, or nobody at all, and the
pull request stalls.
