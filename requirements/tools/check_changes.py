import argparse
import fnmatch
import re
import subprocess
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Literal, NamedTuple, Optional, Set

from packaging.version import Version

HERE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
REPODIR = (HERE / ".." / "..").resolve()


@contextmanager
def printing_table(columns: List[str]):
    print("|" + "|".join(columns) + "|")
    print("|" + "|".join(["-" * len(c) for c in columns]) + "|")

    yield

    # print("|" + "|".join(["-" * len(c) for c in columns]) + "|")


BEFORE_PATTERN = re.compile(r"^-([\w-]+)==([0-9\.post]+)")
AFTER_PATTERN = re.compile(r"^\+([\w-]+)==([0-9\.post]+)")
DIFF_PATTERN = re.compile(r"diff --git a\/([\w_\.\-\/]+\.txt) b\/([\w_\.\-\/]+\.txt)")


def dump_changes(filename: Path):
    if filename.exists():
        filename.unlink()
    command = f"""
    git fetch upstream && \
    git --no-pager diff upstream/master..$(git rev-parse --abbrev-ref HEAD) > {filename}
    """

    subprocess.run(
        command,
        shell=True,
        check=True,
    )


def tag_upgrade(from_version: Version, to_version: Version):
    if from_version.major < to_version.major:
        return "**MAJOR**"
    if from_version.minor < to_version.minor:
        return "*minor*"
    if from_version > to_version:
        return "🔥 downgrade"
    return ""


def parse_changes(filename: Path):
    changes = []
    before = defaultdict(list)
    after = defaultdict(list)
    lib2reqs = defaultdict(list)
    file_a = None
    with filename.open() as fh:
        for line in fh:
            if match := DIFF_PATTERN.match(line):
                file_a, file_b = match.groups()
                assert (
                    file_a == file_b
                ), f"Should compare same files but {file_a}!={file_b}"
            elif match := BEFORE_PATTERN.match(line):
                name, version = match.groups()
                before[name].append(Version(version))
                changes.append(name)
                #
                if file_a:
                    lib2reqs[name].append(file_a)
            elif match := AFTER_PATTERN.match(line):
                name, version = match.groups()
                after[name].append(Version(version))
    return before, after, Counter(changes), lib2reqs


class ReqsClassification(NamedTuple):
    module_type: str  # Literal["packages", "api", "services", "tests"]
    module_name: str
    reqs_type: str  # Literal["base", "test", "tools"]


def classify_reqs_path(reqs_path: str) -> ReqsClassification:

    if (
        any(k in reqs_path for k in ("_test.txt", "requirements.txt"))
        or "test" in reqs_path
    ):
        reqs_type = "test"
    else:
        reqs_type = reqs_path.split("/")[-1].replace(".txt", "").strip("_")

    parts = reqs_path.split("/")
    module_type, module_name = parts[:2]

    return ReqsClassification(module_type, module_name, reqs_type)


def format_classification(c: ReqsClassification):
    color = "blue"
    if c.module_type == "service" and c.reqs_type not in ("test", "tools"):
        color = "red"
    elif c.reqs_type == "tools":
        color = "green"
    return f'<span style="color:{color}">{c.module_name}</span>'


def main_changes_stats() -> None:

    filepath = Path("changes.ignore.keep.log")
    if not filepath.exists():
        dump_changes(filepath)

    before, after, counts, lib2reqs = parse_changes(filepath)

    # format
    print("## Changes to libraries (only updated libraries are included)")
    print("- #packages before:", len(before))
    print("- #packages after :", len(after))
    print()

    COLUMNS = ["#", "name", "before", "after", "upgrade", "count", "packages"]

    with printing_table(COLUMNS):

        for i, name in enumerate(sorted(before.keys()), start=1):
            # TODO: where are these libraries?
            # TODO: are they first dependencies?
            # TODO: if major, get link to release notes
            from_versions = set(str(v) for v in before[name])
            to_versions = set(str(v) for v in after[name])

            used_in_modules = []
            if req_paths := lib2reqs.get(name):
                for rp in req_paths:
                    c = classify_reqs_path(rp)
                    used_in_modules.append(format_classification(c))

            print(
                "|",
                f"{i:3d}",
                "|",
                f"{name:25s}",
                "|",
                f'{", ".join(from_versions):15s}',
                "|",
                f'{",".join(to_versions) if to_versions else "🗑️ removed":10s}',
                "|",
                # how big the version change is
                f"{tag_upgrade(sorted(set(before[name]))[-1], sorted(set(after[name]))[-1]):10s}"
                if to_versions
                else "",
                "|",
                counts[name],
                "|",
                ",".join(used_in_modules),
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


def repo_wide_changes(exclude: Optional[Set] = None) -> None:
    reqs = parse_dependencies(REPODIR, exclude=exclude)

    # format
    print("## Repositroy-wide overview of libraries")
    print("- #reqs files parsed:", len(reqs))
    print()

    deps = defaultdict(lambda: defaultdict(list))
    for r in reqs:
        for name, version in r.dependencies.items():
            deps[name]["name"] = name
            deps[name][r.target].append(version)

    with printing_table(
        columns=["#", "name", "versions-base", "versions-test", "versions-tool"]
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


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI to use")
    parser.add_argument("--changed-reqs", action="store_true", help="print oly changed")
    args = parser.parse_args()

    if args.changed_reqs:
        main_changes_stats()
    else:
        repo_wide_changes(exclude={"*/director/*"})


if __name__ == "__main__":
    main()
