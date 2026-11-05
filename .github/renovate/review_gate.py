#!/usr/bin/env -S uv run --script --no-project
# /// script
# requires-python = ">=3.14"
# dependencies = [] # stdlib-only on purpose: the gate runs every 15 minutes and reads the
#                   # API through gh, so it has nothing to install
# ///
# ruff: noqa: T201  # what the poll decided is reported on stdout, which the Actions run keeps as its log
"""Renovate review gate, run by the review-gate job of
.github/workflows/chore-renovate.yml every 15 minutes.

Renovate opens every PR as a draft (draftPR in .renovaterc.jsonc), so GitHub
does not auto-request the code owners until the checks are done. This poller
marks the drafts ready once their checks have all finished; the ready
transition makes GitHub request the code owners from CODEOWNERS by itself:
- all checks done + passed + 🤖-renovate-fast-lane (patch/pin/digest bumps,
  Python minors, security fixes): the request comes out but nothing waits on
  it, the renovate-fast Mergify queue merges the PR;
- all checks done + passed without the label (majors, other minors): the
  requested review is what the PR then waits for;
- failing checks: nothing for FAIL_COOLDOWN_HOURS on the last commit, so
  Renovate can push its own fix; then the PR gets 🤖-do-not-merge, loses
  🤖-renovate-fast-lane, is marked ready (which requests the owners), and a
  comment lists the failing checks. It then goes through the reviewed queue,
  also once a fix makes its checks pass.
A draft that already has requested reviewers or reviews is left alone: the gate
reported it before or a person handles it (e.g. turned it back into a draft on
purpose).
Each draft also gets a comment listing the lockfile pins its diff moved besides
the dependency named in the title, each with what carried the new version,
updated in place on later runs. It changes no label and no ready state.

Required environment: REPO, BOT, FAIL_COOLDOWN_HOURS. DRIFT_LIST_LIMIT is the
number of packages the comment lists before it truncates and defaults to 40.

Every call goes through gh, so GH_TOKEN must be set and must belong to the
Renovate App: a GitHub App cannot mark a pull request opened by another App
ready, so a github.token (github-actions App) run fails on the ready call.

The `# via` block format it parses is pip-compile's, documented in
docs/renovate.md; see moved_pins below.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated, Final

if TYPE_CHECKING:
    # documentation metadata only, and `annotated-types` is not a dependency of this
    # script: `from __future__ import annotations` keeps these annotations from ever
    # being evaluated at runtime
    from annotated_types import doc

DRIFT_MARKER: Final[
    Annotated[
        str,
        doc(
            "First line of the moved-packages comment; the next poll finds its comment by it and updates that one"
            " instead of adding another"
        ),
    ]
] = "<!-- renovate-drift-summary -->"

FAST_LANE_LABEL: Final[
    Annotated[str, doc("Label of the pull requests the renovate-fast Mergify queue merges without reviews")]
] = "🤖-renovate-fast-lane"

DO_NOT_MERGE_LABEL: Final[
    Annotated[str, doc("Label that keeps a pull request out of both queues until a person removes it")]
] = "🤖-do-not-merge"

ARTIFACT_CHECK: Final[
    Annotated[
        str,
        doc(
            "Report of one lockfile's compile, which fails while the layer it takes as --constraint still pins the"
            " old version; .github/renovate/resync_lockfiles.py re-resolves the tree after it, so it is advisory"
            " here and the [sys] environment setup tests are what gate it"
        ),
    ]
] = "renovate/artifacts"

_HEADLINE_VERSION: Final[
    Annotated[
        re.Pattern[str],
        doc(
            'The version the title names, "Update dependency redis to v7.4.1 [Renovate]" -> 7.4.1. Any other'
            " wording yields nothing, and then that package shows up in the list as well"
        ),
    ]
] = re.compile(r".* to v{1,}([0-9][^ ]*) ")

_PIN: Final[
    Annotated[
        re.Pattern[str],
        doc(
            "A lockfile pin. It can only start at column 1, so the hunk of another file cannot match it, and"
            " extras (`uvicorn[standard]==1.2`) name the same package"
        ),
    ]
] = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?==([A-Za-z0-9._+!-]+)")

_REFERENCE: Final[
    Annotated[re.Pattern[str], doc("A `# via` entry that names a consumed file instead of a package")]
] = re.compile(r"^-{1,2}(?:constraint|requirement|[cr])(?:[ \t=]|$)")

_COMMENT_PAGE_SIZE: Final[Annotated[int, doc("issues/comments returns at most 100 comments per page")]] = 100

_FIXING_DOCS: Final[
    Annotated[
        str,
        doc("Where a reviewer is pointed to for taking over or closing a failing pull request"),
    ]
] = "docs/renovate.md#fixing-a-failing-renovate-pull-request"


def gh(*args: str) -> subprocess.CompletedProcess[str]:
    """Runs gh. The App token comes from GH_TOKEN in the environment"""
    return subprocess.run(  # noqa: S603
        ["gh", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )


def gh_json(*args: str) -> object:
    """The JSON gh writes for a read call"""
    return json.loads(gh(*args).stdout or "null")


@dataclass(frozen=True, slots=True)
class Check:
    """One check run as `gh pr checks --json name,bucket` reports it"""

    name: str
    bucket: str


@dataclass(slots=True)
class PullRequest:
    """A draft pull request and everything the gate read about it"""

    number: int
    repo: str
    title: str = ""
    labels: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()

    def api(self, path: str) -> object:
        return gh_json("api", f"repos/{self.repo}/{path}")

    def has_reviewers(self) -> bool:
        """Whether reviewers were requested or already reviewed: the gate reported this
        pull request before, or a person is handling it"""
        requested = self.api(f"pulls/{self.number}/requested_reviewers")
        reviews = self.api(f"pulls/{self.number}/reviews")
        assert isinstance(requested, dict)
        assert isinstance(reviews, list)
        return len(requested.get("users", [])) + len(requested.get("teams", [])) + len(reviews) > 0

    def read(self) -> None:
        """Fills in title, labels and checks. A pull request with no checks reported yet
        keeps an empty list"""
        info = gh_json("pr", "view", f"{self.number}", "--repo", self.repo, "--json", "labels,title")
        assert isinstance(info, dict)
        self.title = str(info.get("title", ""))
        self.labels = tuple(str(label["name"]) for label in info.get("labels", []))
        try:
            reported = gh_json("pr", "checks", f"{self.number}", "--repo", self.repo, "--json", "name,bucket")
        except subprocess.CalledProcessError:
            reported = []
        assert isinstance(reported, list)
        self.checks = tuple(Check(name=c["name"], bucket=c["bucket"]) for c in reported if c["name"] != ARTIFACT_CHECK)

    def age_hours(self) -> int:
        """Hours since the last commit of its head, whole hours rounded down"""
        head = gh_json("pr", "view", f"{self.number}", "--repo", self.repo, "--json", "headRefOid")
        assert isinstance(head, dict)
        commit = self.api(f"commits/{head['headRefOid']}")
        assert isinstance(commit, dict)
        committed = datetime.fromisoformat(str(commit["commit"]["committer"]["date"])).astimezone(UTC)
        return max(0, int((datetime.now(UTC) - committed).total_seconds() // 3600))

    def mark_ready(self) -> None:
        gh("pr", "ready", f"{self.number}", "--repo", self.repo)

    def comment(self, body: str) -> None:
        gh("pr", "comment", f"{self.number}", "--repo", self.repo, "--body", body)

    def set_labels(self, *, add: str = "", remove: str = "") -> None:
        args = ["pr", "edit", f"{self.number}", "--repo", self.repo]
        if add:
            args += ["--add-label", add]
        if remove:
            args += ["--remove-label", remove]
        gh(*args)


def _normalized(name: str) -> str:
    """PEP 503-normalized name, extras dropped: `uvicorn[standard]` and `Uvicorn` are one package"""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True, slots=True)
class _Lockfile:
    """Where the lockfile currently being read sits, which is what makes the paths of its
    `# via` block resolvable"""

    base: str
    own_dir: str

    @classmethod
    def of(cls, lockfile: str) -> _Lockfile:
        """From the lockfile's repository path. `base` is the directory `make reqs` runs in
        and the one the `# via` paths are relative to, which is not the directory holding
        the file"""
        parts = lockfile.split("/")
        return cls(base="/".join(parts[:-2]), own_dir="/".join(parts[:-1]))

    def resolve(self, path: str) -> str:
        parts = [part for part in self.base.split("/") if part]
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        return "/".join(parts)

    def counted_as(self, path: str) -> tuple[str, str]:
        """The resolved path and why this file carried the new version: a file of another
        requirements directory is the constraint the resolve had to honour, the directory's
        own layer is weaker evidence"""
        full = self.resolve(path)
        if not full:
            return "", ""
        kind = "own" if str(PurePosixPath(full).parent) == self.own_dir else "outside"
        return kind, full


@dataclass(slots=True)
class _MovedPins:
    """Everything one pull request diff says about pins that moved, and why

    Only `moved_pins` uses it. A pin moves in dozens of lockfiles of one pull request, so
    each version is kept once per package, and the reasons are counted over the whole pull
    request instead of taken from the first lockfile that mentions one.
    """

    seen: set[str] = field(default_factory=set)
    old: dict[str, list[str]] = field(default_factory=dict)
    new: dict[str, list[str]] = field(default_factory=dict)
    outside: Counter[tuple[str, str]] = field(default_factory=Counter)
    requiring: Counter[tuple[str, str]] = field(default_factory=Counter)
    own: Counter[tuple[str, str]] = field(default_factory=Counter)
    lockfile: _Lockfile | None = None
    pending: str = ""
    in_via_block: bool = False

    def add_reason(self, name: str, entry: str) -> None:
        """Records one entry of a `# via` block: a consumed file, or the package requiring it"""
        entry = entry.rstrip()
        if not entry:
            return
        if _REFERENCE.match(entry):
            assert self.lockfile
            path = re.sub(r"^--?(?:constraint|requirement)[ \t=]*|^-[cr][ \t=]*", "", entry)
            kind, full = self.lockfile.counted_as(path)
            if kind == "own":
                self.own[(name, full)] += 1
            elif kind == "outside":
                self.outside[(name, full)] += 1
            return
        package = re.sub(r"[<>=!~].*$", "", entry)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package):
            self.requiring[(name, _normalized(package))] += 1

    def consume(self, line: str) -> None:
        """Reads one line of a pull request diff"""
        if line.startswith("diff --git "):
            self.pending, self.in_via_block = "", False
            return
        if line.startswith("+++ "):
            self.lockfile = _Lockfile.of(_diff_header_path(line))
            self.pending, self.in_via_block = "", False
            return
        side, text = line[:1], line[1:]
        if side not in ("+", " ", "-"):
            return  # a hunk header or another diff line, which cannot carry a lockfile line
        if side == "-":
            self.pending, self.in_via_block = "", False
            self.removed(text)
            return
        if not self.pinned(side, text) and not self.commented(text):
            self.in_via_block = False

    def removed(self, line: str) -> None:
        """Reads a removed pin. Only a package whose pin also appears on the added side of
        the pull request counts as moved"""
        if (pin := _pin_of(line)) is None:
            return
        name, version = pin
        self.seen.add(name)
        olds = self.old.setdefault(name, [])
        if version not in olds:
            olds.append(version)

    def pinned(self, side: str, line: str) -> bool:
        """Reads an added or unchanged pin line. Returns whether the line is one"""
        if (pin := _pin_of(line)) is None:
            return False
        name, version = pin
        # an unchanged pin (a context line) ends the block of the pin above it
        self.pending = name if side == "+" else ""
        self.in_via_block = False
        if side == "+":
            news = self.new.setdefault(name, [])
            if version not in news:
                news.append(version)
        return True

    def commented(self, line: str) -> bool:
        """Reads an entry of the `# via` block under the pin last added. Returns whether the
        line is one"""
        if not self.pending or not re.match(r"[ \t]*#", line):
            return False
        entry = re.sub(r"^[ \t]*#[ \t]*", "", line)
        if re.match(r"via([ \t]|$)", entry):
            if entry := re.sub(r"^via[ \t]*", "", entry):
                self.add_reason(self.pending, entry)
            else:
                # the entries of the block follow on the next lines
                self.in_via_block = True
            return True
        if self.in_via_block:
            self.add_reason(self.pending, entry)
            return True
        return False

    def reason(self, name: str) -> str:
        """What carried the new version: the most frequent candidate of the strongest kind
        that has one, alphabetically first when counts tie"""
        for tally in (self.outside, self.requiring, self.own):
            candidates = [value for (key, value) in tally if key == name]
            if candidates:
                return min(candidates, key=lambda value: (-tally[(name, value)], value))
        return ""

    def lines(self, headline: str = "") -> list[str]:
        """One "<name>: <olds> -> <news>[\\t<reason>]" line per package whose pin moved.
        Left out: a package the diff only adds or only drops, a pin it touches without
        changing it, and the version the title names"""
        listed = []
        for name in sorted(self.seen):
            olds, news = self.old.get(name, []), self.new.get(name, [])
            if not olds or not news or (headline and headline in news):
                continue
            line = f"{name}: {', '.join(olds)} -> {', '.join(news)}"
            if reason := self.reason(name):
                line = f"{line}\t{reason}"
            listed.append(line)
        return listed


def _pin_of(line: str) -> tuple[str, str] | None:
    """The (name, version) of a lockfile pin line, or None if it is not one"""
    match = _PIN.match(line)
    if not match:
        return None
    name, _, version = match.groups()
    return _normalized(name), version.rstrip()


def _diff_header_path(line: str) -> str:
    """The new file of a `+++ b/<path>` line, with the timestamp git may append removed"""
    path = line[len("+++ ") :]
    path = re.sub(r"^[ab]/", "", path)
    return re.sub(r"[ \t].*$", "", path)


def moved_pins(diff: str, headline: str = "") -> list[str]:
    """The packages whose lockfile pin a pull request diff moved, sorted

    Reads the diff of a pull request and returns one line per package, sorted, as
    "<name>: <old>[, <old>...] -> <new>[, <new>...]" plus, after a tab, why a lockfile now
    carries the new version.

    The reason comes from the `# via` block under the moved pin, which names the file that
    constrained it (`-c`/`-r`) or the package requiring it. A file of another requirements
    directory wins over a requiring package, since that file is the constraint the resolve
    had to honour; then a requiring package; then the directory's own layer. Candidates are
    counted over every lockfile of the pull request and the most frequent one of the
    winning kind is reported. The reason is left empty when the diff gives no clue.
    """
    state = _MovedPins()
    for line in diff.splitlines():
        state.consume(line)
    return state.lines(headline)


def headline_version(title: str) -> str:
    """The version the title names: the package of that version is what the pull request is
    about, so it is not drift"""
    if match := _HEADLINE_VERSION.search(title):
        return match.group(1)
    return ""


def listed_pins(lines: Iterable[str]) -> str:
    """The moved pins as a markdown list, each with what carried its new version"""
    entries = []
    for line in lines:
        name, _, reason = line.partition("\t")
        entries.append(f"- `{name}` — via `{reason}`" if reason else f"- `{name}`")
    return "\n".join(entries)


def drift_comment(repo: str, pins: list[str], list_limit: int) -> str:
    """The comment body listing the moved pins, truncated at `list_limit` entries"""
    listed = listed_pins(pins[:list_limit])
    if len(pins) > list_limit:
        listed += f"\n- and {len(pins) - list_limit} more"
    return (
        f"{DRIFT_MARKER}\n\n"
        "> [!NOTE]\n"
        f"> The lockfile resync moved **{len(pins)}** package(s) besides the one this pull request is about:"
        " it regenerates every `requirements/` directory the pin reaches. Each line names the file or the"
        " package that carried the new version. Nothing else moves.\n\n"
        f"{listed}\n\n"
        f"If one of these is what breaks a check, fix its cause on `master` as described in"
        f" https://github.com/{repo}/blob/master/{_FIXING_DOCS}."
    )


def drift_comment_id(pr: PullRequest) -> object:
    """The id of the comment an earlier run left, found by its first line, or None. Paged
    because a pull request the gate held has that comment on an earlier page than the
    drift one"""
    for page in count(1):
        batch = pr.api(f"issues/{pr.number}/comments?per_page={_COMMENT_PAGE_SIZE}&page={page}")
        assert isinstance(batch, list)
        for comment in batch:
            if str(comment["body"]).startswith(DRIFT_MARKER):
                return comment["id"]
        if len(batch) < _COMMENT_PAGE_SIZE:
            return None
    return None


def post_drift_comment(pr: PullRequest, body: str) -> bool:
    """Adds the comment, or edits the one an earlier run left. Whether it wrote anything:
    the body is compared so a pull request whose diff did not change does not get a new
    notification every 15 minutes"""
    existing = drift_comment_id(pr)
    if existing is None:
        pr.comment(body)
        return True
    current = pr.api(f"issues/comments/{existing}")
    assert isinstance(current, dict)
    if current["body"] == body:
        return False
    gh("api", "-X", "PATCH", f"repos/{pr.repo}/issues/comments/{existing}", "-f", f"body={body}")
    return True


def hold_for_review(pr: PullRequest, age_hours: int, failing: list[str]) -> None:
    """Marks a pull request that kept failing past the cool-down ready and holds it with
    🤖-do-not-merge, so it goes through the reviewed queue instead of the fast lane"""
    failed = "\n".join(f"- {name}" for name in failing)
    pr.set_labels(add=DO_NOT_MERGE_LABEL, remove=FAST_LANE_LABEL if FAST_LANE_LABEL in pr.labels else "")
    pr.mark_ready()
    pr.comment(
        "> [!WARNING]\n"
        f"> The checks have been failing for {age_hours} h on the last commit and Renovate did not fix them."
        f" This pull request is held with {DO_NOT_MERGE_LABEL} and needs reviews, also if a later commit passes."
        f"\n\nFailing checks:\n\n{failed}\n\n"
        f"Reviewers: do not push to this branch; fix or close it as described in"
        f" https://github.com/{pr.repo}/blob/master/{_FIXING_DOCS}, and remove {DO_NOT_MERGE_LABEL} once the"
        f" checks pass and the update is fine to merge. {FAST_LANE_LABEL} was removed with the hold; add it back"
        " to send the pull request through the fast lane."
    )


def open_drafts(repo: str, bot: str) -> list[int]:
    """Open draft pull requests of the bot. --author filters server-side; GitHub search
    resolves the bot name to both the "<name>[bot]" and the "app/<name>" form the gh CLI
    reports in .author.login. --limit: the default 30 results would drop drafts once the
    repository has more open pull requests than that"""
    pulls = gh_json(
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "open",
        "--base",
        "master",
        "--limit",
        "200",
        "--author",
        bot,
        "--json",
        "number,isDraft",
    )
    assert isinstance(pulls, list)
    return [int(pull["number"]) for pull in pulls if pull["isDraft"]]


def gate_draft(pr: PullRequest, fail_cooldown_hours: int, drift_list_limit: int) -> None:
    """What the poll does with one draft pull request whose checks are all done"""
    if failing := [check.name for check in pr.checks if check.bucket == "fail"]:
        # Renovate pushes fixes itself; request a review only once it stops trying
        age_hours = pr.age_hours()
        if age_hours < fail_cooldown_hours:
            print(f"PR #{pr.number}: failing for {age_hours}h, waiting for Renovate to fix it")
            return
        hold_for_review(pr, age_hours, failing)
        print(f"PR #{pr.number}: failing past the cool-down, held and marked ready")
    else:
        pr.mark_ready()
        if FAST_LANE_LABEL in pr.labels:
            print(f"PR #{pr.number}: checks passed, the renovate-fast queue takes it without waiting for reviews")
        else:
            print(f"PR #{pr.number}: checks passed, marked ready for review")

    # last, so a pull request that moved out of the drafts this pass cannot get a second
    # comment before its checks even ran
    pins = moved_pins_from(pr)
    if pins and post_drift_comment(pr, drift_comment(pr.repo, pins, drift_list_limit)):
        print(f"PR #{pr.number}: commented the {len(pins)} packages the resync moved")


def moved_pins_from(pr: PullRequest) -> list[str]:
    """The pins the resync moved on top of the package of the title. The resync commits
    inside Renovate's own run, before the pull request exists, so it cannot say so itself"""
    try:
        diff = gh("pr", "diff", f"{pr.number}", "--repo", pr.repo).stdout
    except subprocess.CalledProcessError:
        print(f"PR #{pr.number}: diff not readable, skipping the moved-packages comment")
        return []
    return moved_pins(diff, headline_version(pr.title))


def run(repo: str, bot: str, fail_cooldown_hours: int, drift_list_limit: int) -> None:
    """One pass of the poll over the bot's draft pull requests"""
    drafts = open_drafts(repo, bot)
    if not drafts:
        print(f"no draft {bot} pull requests open")
    for number in drafts:
        pr = PullRequest(number=number, repo=repo)
        if pr.has_reviewers():
            print(f"PR #{pr.number}: draft with reviewers, left to them")
            continue
        pr.read()
        if not pr.checks:
            print(f"PR #{pr.number}: no checks reported yet")
            continue
        if any(check.bucket == "pending" for check in pr.checks):
            print(f"PR #{pr.number}: checks still pending")
            continue
        gate_draft(pr, fail_cooldown_hours, drift_list_limit)


def main() -> int:
    required = ("REPO", "BOT", "FAIL_COOLDOWN_HOURS")
    if missing := [name for name in required if not os.environ.get(name)]:
        print(f"error: missing environment: {' '.join(missing)}", file=sys.stderr)
        return 2
    run(
        repo=os.environ["REPO"],
        bot=os.environ["BOT"],
        fail_cooldown_hours=int(os.environ["FAIL_COOLDOWN_HOURS"]),
        drift_list_limit=int(os.environ.get("DRIFT_LIST_LIMIT", "40")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
