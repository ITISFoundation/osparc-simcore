import fnmatch
import os
import re
import subprocess
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Literal, NamedTuple, Optional, Set

from packaging.version import Version


@contextmanager
def printing_table(columns: List[str]):
    print("|" + "|".join(columns) + "|")
    print("|" + "|".join(["-" * len(c) for c in columns]) + "|")

    yield

    # print("|" + "|".join(["-" * len(c) for c in columns]) + "|")


BEFORE_PATTERN = re.compile(r"^-([\w-]+)==([0-9\.post]+)")
AFTER_PATTERN = re.compile(r"^\+([\w-]+)==([0-9\.post]+)")


def dump_changes(filename: Path):
    subprocess.run(f"git --no-pager diff > {filename}", shell=True, check=True)


def tag_upgrade(from_version: Version, to_version: Version):
    assert from_version < to_version
    if from_version.major < to_version.major:
        return "**MAJOR**"
    if from_version.minor < to_version.minor:
        return "*minor*"
    return ""


def parse_changes(filename: Path):
    changes = []
    before = defaultdict(list)
    after = defaultdict(list)
    with filename.open() as fh:
        for line in fh:
            if match := BEFORE_PATTERN.match(line):
                name, version = match.groups()
                before[name].append(Version(version))
                changes.append(name)
            elif match := AFTER_PATTERN.match(line):
                name, version = match.groups()
                after[name].append(Version(version))
    return before, after, Counter(changes)


def main_changes_stats():

    filepath = Path("changes.ignore.keep.log")
    if not filepath.exists():
        dump_changes(filepath)

    before, after, counts = parse_changes(filepath)

    # format
    print("Overview of changes in dependencies")
    print("- #packages before:", len(before))
    print("- #packages after :", len(after))
    print()

    COLUMNS = ["#", "name", "before", "after", "upgrade", " count"]

    with printing_table(COLUMNS):

        for i, name in enumerate(sorted(before.keys()), start=1):
            # TODO: where are these libraries?
            # TODO: are they first dependencies?
            # TODO: if major, get link to release notes
            from_versions = set(str(v) for v in before[name])
            to_versions = set(str(v) for v in after[name])

            print(
                "|",
                f"{i:3d}",
                "|",
                f"{name:25s}",
                "|",
                f'{", ".join(from_versions):15s}',
                "|",
                f'{",".join(to_versions) if to_versions else "removed":10s}',
                "|",
                # how big the version change is
                f"{tag_upgrade(sorted(set(before[name]))[-1], sorted(set(after[name]))[-1]):10s}"
                if to_versions
                else "",
                "|",
                counts[name],
                "|",
            )


## Stats on installed packages (i.e. defined in txt files)
DEPENDENCY = re.compile(r"([\w_-]+)==([0-9\.-]+)")


def parse_dependencies_in_reqfile(reqfile: Path) -> Dict[str, Version]:
    name2version = {}
    for name, version in DEPENDENCY.findall(reqfile.read_text()):
        # TODO: typing-extensions==4.0.1 ; python_version < "3.9" might intro multiple versions
        assert name not in name2version, f"{name} more than once in {reqfile}"
        name2version[name] = Version(version)
    return name2version


class ReqFile(NamedTuple):
    path: Path
    target: Literal["base", "test", "tool", "other"]
    dependencies: Dict[str, Version]


def parse_dependencies(
    repodir: Path, *, exclude: Optional[Set] = None
) -> List[ReqFile]:
    reqs = []
    exclude = exclude or set()
    for reqfile in repodir.rglob("**/requirements/_*.txt"):
        if any(fnmatch.fnmatch(reqfile, x) for x in exclude):
            continue
        try:
            t = {"_base.txt": "base", "_test.txt": "test", "_tools.txt": "tool"}[
                reqfile.name
            ]
        except KeyError:
            if "test" in f"{reqfile.parent}":
                t = "test"
            else:
                t = "other"

        reqs.append(
            ReqFile(
                path=reqfile,
                target=t,
                dependencies=parse_dependencies_in_reqfile(reqfile),
            )
        )
    return reqs


def main_dep_stats(exclude: Optional[Set] = None):
    repodir = Path(os.environ.get("REPODIR", "."))
    reqs = parse_dependencies(repodir, exclude=exclude)

    # format
    print("Overview of libraries used repo-wide")
    print("- #reqs files parsed:", len(reqs))
    print()

    deps = defaultdict(lambda: defaultdict(list))
    for r in reqs:
        for name, version in r.dependencies.items():
            deps[name]["name"] = name
            deps[name][r.target].append(version)

    with printing_table(
        columns=["#", "name", "versions-base", "versions-test", "versons-tool"]
    ):
        for i, name in enumerate(sorted(deps.keys()), start=1):

            def _norm(thing):
                return [f"{v}" for v in sorted(list(set(thing)))]

            bases = _norm(deps[name]["base"])
            tests = _norm(deps[name]["test"])
            tools = _norm(deps[name]["tool"])

            print(
                "|",
                f"{i:3d}",
                "|",
                f"{name:25s}",
                "|",
                f'{", ".join(bases):25s}',
                "|",
                f'{", ".join(tests):25s}',
                "|",
                f'{", ".join(tools):25s}',
                "|",
            )


if __name__ == "__main__":
    # main_changes_stats()
    main_dep_stats(exclude={"*/director/*"})
