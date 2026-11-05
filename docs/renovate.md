# Dependency updates (Renovate)

A self-hosted Renovate updates the dependencies in this repository: Python
lockfiles, Docker images, GitHub Actions, `uv`, and the Python patch version.
Neither the Mend-hosted app nor Dependabot opens them. Dependabot alerts stay on
as a vulnerability source only.

| What | Where |
| --- | --- |
| Runner and review gate (one job each) | [.github/workflows/chore-renovate.yml](../.github/workflows/chore-renovate.yml) |
| Repository configuration | [.renovaterc.jsonc](../.renovaterc.jsonc) |
| Admin configuration (`allowedCommands`, `platformCommit`) | [.github/renovate/global-config.json5](../.github/renovate/global-config.json5) |
| Lockfile re-resolution post-upgrade task | [.github/renovate/resync_lockfiles.py](../.github/renovate/resync_lockfiles.py) |
| Review gate script (drafts go ready) | [.github/renovate/review_gate.sh](../.github/renovate/review_gate.sh) |
| Who reviews them | [CODEOWNERS](../.github/CODEOWNERS), last block |
| Who merges them | [mergify.yml](../.github/mergify.yml) |

Renovate runs as the GitHub App `osparc-simcore-renovate[bot]`. That App signs
its commits and runs `make reqs` as a post-upgrade task, which the hosted
Renovate cannot do. Do not push a fixup commit under another author. CI waits
for approval before running a commit it did not sign, and Renovate stops
touching a branch that someone else wrote last. Mergify's merge commits are the
exception (`gitIgnoredAuthors`, see below).

The `renovate` job runs:

- nightly at 02:17 UTC;
- on a push to `master` that changes a file Renovate manages (the paths of the
  last CODEOWNERS block) or its configuration, so the other open Renovate pull
  requests are rebased right after a merge;
- when a person edits the Dependency Dashboard or ticks the rebase box of a
  Renovate pull request;
- on demand (*Run workflow*, job `renovate`).

The `review-gate` job runs every 15 minutes and does not run Renovate. New
Renovate pull requests get the current milestone from
[chore-labeler.yml](../.github/workflows/chore-labeler.yml), like every other
pull request.

## Update policies

- **Security fixes skip the throttling.** `osvVulnerabilityAlerts` and the
  Dependabot alerts open the pull request on the next run. It needs no
  Dependency Dashboard approval and waits for no cool-down. It gets the
  `security` label and `🤖-renovate-fast-lane`, so a security fix whose checks pass
  merges through the fast lane (see below) whatever the version jump.
  `vulnerabilityFixStrategy: "highest"` makes it propose the
  newest release, not the lowest one that fixes the vulnerability. A branch then
  cannot offer two versions of the same package.
- **Regular updates are throttled.** Two new pull requests per hour, four open
  at a time. The Dependency Dashboard holds the rest. It is also where you tick
  Docker image majors and the monthly `lockFileMaintenance` runs; majors of
  Python packages, GitHub Actions and `uv` arrive as regular pull requests.
- **Cool-downs.** 14 days for every dependency: pip-compile lockfiles, GitHub
  Actions, and `uv`. Security fixes skip them.
- **One PR per dependency.** A pip-compile package gets a single PR that moves
  its pin in every `requirements/` directory at once (the resync post-upgrade
  task propagates it). No PRs grouped per directory or per area. The
  exceptions move a family in one PR (majors on their own branch): the
  `opentelemetry-*` packages, which ship in two coordinated release trains that
  pin each other (`renovate/opentelemetry`); the AWS SDK (`boto3`, `botocore`,
  `s3transfer`, `aioboto3`, `aiobotocore`) with its stubs (`renovate/boto`); the
  other type stubs (`types-*`, `*-stubs`, `renovate/type-stubs`); and the
  `pytest-*` plugins (`renovate/pytest-plugins`). Security pull
  requests are never grouped: Renovate's `vulnerabilityAlerts` default resets
  the group name, so a vulnerable package gets its own immediate PR.

## From pull request to merge

How each kind of pull request reaches `master`:

```mermaid
flowchart TD
    human["Human PR"]
    fast["Renovate: patch, pin, digest,<br/>Python minor, security fix<br/>(🤖-renovate-fast-lane)"]
    other["Renovate: major,<br/>non-Python minor"]
    gate{"review gate, every 15 min:<br/>checks of the draft"}
    ready["ready: GitHub requests<br/>the code owners"]
    held["ready, 🤖-do-not-merge,<br/>fast-lane label removed"]
    fastq["renovate-fast queue:<br/>checks only"]
    defq["default queue: 2 approvals,<br/>one by a code owner, checks"]
    merge["Mergify merges master in,<br/>CI runs again, squash-merge"]

    human -- "opened or marked ready" --> defq
    fast -- "draft" --> gate
    other -- "draft" --> gate
    gate -- "passed" --> ready
    gate -- "failing for 3 h" --> held
    held -- "fixed, reviewed,<br/>label removed" --> defq
    ready -- "fast-lane label" --> fastq
    ready -- "other Renovate PRs" --> defq
    fastq --> merge
    defq --> merge
```

Every commit runs CI Build Test. Chore Rerun Flaky Jobs retries the failed jobs
of a run once, when it is the first attempt on a pull request from a fork, a
Renovate pull request (drafts included) or `master`, 1 to 3 jobs failed, and
none of them is linting or a typecheck. A human pull request from this
repository is retried by hand:

```mermaid
flowchart LR
    commit["new commit"]
    ci["CI Build Test"]
    pass["checks pass"]
    flaky{"eligible for<br/>a retry?"}
    rerun["Chore Rerun Flaky Jobs:<br/>reruns failed jobs once"]
    fail["checks fail"]

    commit --> ci
    ci -- "passed" --> pass
    ci -- "failed" --> flaky
    flaky -- "yes" --> rerun
    rerun --> ci
    flaky -- "no" --> fail
```

Renovate never merges. `automerge` stays `false`. Mergify merges its pull
requests, either reviewed or through a fast lane, and reviewers are requested
only after the checks have finished:

1. Renovate opens every pull request as a draft (`draftPR`), so GitHub does not
   auto-request the code owners up front — security pull requests included.
2. The `review-gate` job polls the drafts every 15 minutes. Once all
   checks of the head commit are done, it marks the pull request ready — and the
   ready transition makes GitHub request the code owners itself:
   - **all passed, `🤖-renovate-fast-lane` label** (patch, pin and digest bumps,
     Python minors, and every security fix): the `renovate-fast` Mergify queue
     merges it without waiting for that review — the request goes out, nothing
     blocks on it. GitHub does not let anyone withdraw a code-owner request, so
     it stays until the merge;
   - **all passed, no label** (majors, other minors): the requested
     code-owner review is what the pull request then waits for;
   - **failing**: nothing for 3 h so Renovate can push its own fix. If the last
     commit is still failing, the pull request gets `🤖-do-not-merge`, loses
     `🤖-renovate-fast-lane`, is marked ready (which requests the code owners),
     and a warning comment lists the failing checks. From then on it goes
     through the reviewed path, also once a fix makes its checks pass.

   The gate leaves a draft alone once it has requested reviewers or reviews, so
   a pull request turned back into a draft stays a draft.

   Besides marking drafts ready, the gate comments the lockfile pins a pull
   request moved besides the dependency of its title, and updates that comment on
   later runs instead of adding one. It lists them because a "patch" bump rewrites
   dozens of lockfiles, and nothing in the title says so. The comment informs; it
   never holds a pull request back.
3. The reviewed path merges once Mergify's conditions match: the branch is
   up to date with `master` (the ruleset marks the checks *strict*), reviewers
   approve twice, request no changes, leave no thread open, and a code owner
   approves. For the files Renovate writes, the owners are the four people in
   the last block of `.github/CODEOWNERS`. They own *only* version manifests:
   `**/requirements/**`, Dockerfiles, `docker-compose*.yml`, `.python-version`,
   and the Actions pinned under `.github/workflows/**`. One dependency bump
   rewrites dozens of directories at once, so leaving those files to the
   per-service rules would make every security fix wait on six or seven
   reviewers.

Add the `🤖-do-not-merge` label to hold a pull request back, from either lane.
Remove it to let the pull request go; a fast-lane pull request then merges
without waiting for a review. On the reviewed path, anyone else may
still approve, and their review counts toward the two approvals, but it does not
clear the code-owner gate.

How the fast lane gets past the review requirement:

- Mergify copies the rules of the `master` rulesets into the conditions of every
  queue, including the *master-branch-reviews* rule (two approvals, a code
  owner, threads resolved). Being on that ruleset's bypass list only changes what
  GitHub lets Mergify do, not what Mergify waits for. The `renovate-fast` queue
  therefore sets `branch_protection_injection_mode: none`;
- `none` also drops the required checks of the *master branch* ruleset. Instead
  of a copy of the ruleset's list, the queue requires that no check of another
  app than Mergify is pending or failed (`-check-pending~=^@(?!mergify/)`,
  same for `check-failure` except `renovate/artifacts`, see below) and that
  `system-tests` passed. Any other failing check therefore keeps a pull request
  out of the fast lane. The `system-tests` condition keeps the pull request
  waiting until CI has reported on the commit Mergify adds; renaming that job
  stalls the fast lane;
- the fast lane only takes a pull request Renovate wrote alone: Renovate opened
  it, and every commit is authored by Renovate or Mergify and verified by
  GitHub (`renovate_only` in `mergify.yml`). A commit pushed by anyone else
  sends the pull request to the default queue, which waits for reviews; so
  does the label on a human pull request;
- Renovate applies the `🤖-renovate-fast-lane` label. It replaces
  `🤖-automerge`, which no Mergify rule reads anymore.

To fix a failing Renovate pull request, see
[Fixing a failing Renovate pull request](#fixing-a-failing-renovate-pull-request).

A failing `renovate/artifacts` check on its own is not a reason to act. Renovate
compiles every lockfile of a branch on its own, and a lockfile that takes its own
parent layer as a `--constraint` fails whenever Renovate reaches it while that
parent still pins the old version: `Because you require redis==7.4.0 and
redis==7.4.1`. The order the files are compiled in comes out of the file scan, so
the failure lands on whichever lockfile is reached too early, and the resync
post-upgrade task re-resolves the whole tree afterwards anyway. What the check
cannot tell apart from that false alarm is a resync that could not propagate a
pin, which leaves `renovate-resync-report.md` in the pull request — and
`test_no_lockfile_resync_left_behind` of `tests/environment-setup` fails on that
file, which is what keeps a real resync failure out of the fast lane.

What the resync does add to a pull request is movement in other packages. It gets
the dependency of the pull request as an exact pin, so that one never moves, but
uv treats an already pinned version as a preference rather than a requirement:
re-resolving a directory can lift its neighbours. When a directory refuses to
resolve, the resync frees the packages uv blames, up to `MAX_UNBLOCK_ROUNDS`
rounds. A freed package may first rise only as high as another lockfile of this
repository already pins it, and only a round that cannot resolve on that ceiling
lets uv take the newest release. Because directories are regenerated
constraint-sources-first, whatever did move then becomes the constraint every
consumer resolves against, which is how a patch bump ends up rewriting 41
lockfiles. The review gate's checks decide whether such a pull request merges;
the moved pins are commented, not blocked.

## Keeping a pull request up to date

GitHub's *Update branch* button is disabled. Two tools update a Renovate branch:

- **Renovate** rebuilds every branch that is behind `master` or conflicts with
  it on each run (`rebaseWhen` resolves to `behind-base-branch` because the
  ruleset requires up-to-date branches). It redoes the update and the resync task
  on top of `master`, so overlapping pins are regenerated, not merged as text.
  It skips a branch that has a commit by anyone other than itself or Mergify;
  tick the rebase box of the pull request to have it start over;
- **Mergify** tests one pull request at a time on its own branch. When the queue
  conditions match, it merges `master` into the branch, waits for the checks of
  that commit, and squash-merges. That is a plain git merge: two pull requests
  that move the same pins without a textual conflict are not regenerated, and no
  check re-runs pip-compile, so CI only catches pins that fail to install.

A pull request that waits for reviews is only updated by Renovate's runs. The
push trigger of the `renovate` job makes that happen within minutes of every
dependency merge.

## Fixing a failing Renovate pull request

Do not push to a `renovate/*` branch. The fast lane refuses a pull request with
a commit Renovate did not write, and Renovate stops maintaining a branch someone
else committed to, so its lockfiles are no longer regenerated. Instead:

1. **Flaky failure**: tick the rebase box in the pull request description;
   Renovate recreates the branch and CI runs again.
2. **The new version breaks something**: fix the cause on `master` in a pull
   request of your own (code that needs the new API, a constraint in
   `requirements/constraints.txt`, the Renovate configuration). Once it merges,
   Renovate regenerates its branch on top of it.
3. **The update needs code changes in the same commit**: close the Renovate pull
   request and open your own with the update and the fix; it goes through
   review like any other pull request.
4. **The version cannot be used for now**: close the pull request, or exclude
   the version in `.renovaterc.jsonc` (`allowedVersions`, `ignoreDeps`).

A pull request the review gate held keeps `🤖-do-not-merge` after its checks turn
green again, and it lost `🤖-renovate-fast-lane` when it was held. Removing the
first label sends it through the reviewed path; re-adding the second one too
takes it through the fast lane instead.

## Adding something new for Renovate to manage

Add it to the last block of `.github/CODEOWNERS` too, whether it is a new
lockfile directory or a new file that holds a version pin. Otherwise GitHub asks
the owners of every service the pull request touches, or nobody at all, and the
pull request stalls.
