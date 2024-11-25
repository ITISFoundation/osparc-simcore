# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio
import hashlib
import itertools
import os
import secrets
import string
import tempfile
from collections.abc import AsyncIterable, Callable, Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy
import pytest
from faker import Faker
from PIL import Image
from pydantic import ByteSize, TypeAdapter
from pytest_benchmark.plugin import BenchmarkFixture
from servicelib import archiving_utils
from servicelib.archiving_utils import ArchiveError, archive_dir, unarchive_dir
from servicelib.file_utils import remove_directory


def _print_tree(path: Path, level=0):
    tab = " " * level
    print(f"{tab}{'+' if path.is_dir() else '-'} {path if level==0 else path.name}")
    for p in path.glob("*"):
        _print_tree(p, level + 1)


@pytest.fixture
def dir_with_random_content(faker: Faker) -> Iterable[Path]:
    def random_string(length: int) -> str:
        return "".join(secrets.choice(string.ascii_letters) for i in range(length))

    def make_files_in_dir(dir_path: Path, file_count: int) -> None:
        for _ in range(file_count):
            (dir_path / f"{random_string(8)}.bin").write_bytes(
                os.urandom(faker.random_int(1, 10))
            )

    def ensure_dir(path_to_ensure: Path) -> Path:
        path_to_ensure.mkdir(parents=True, exist_ok=True)
        return path_to_ensure

    def make_subdirectory_with_content(subdir_name: Path, max_file_count: int) -> None:
        subdir_name = ensure_dir(subdir_name)
        make_files_in_dir(
            dir_path=subdir_name,
            file_count=faker.random_int(1, max_file_count),
        )

    def make_subdirectories_with_content(
        subdir_name: Path, max_subdirectories_count: int, max_file_count: int
    ) -> None:
        subdirectories_count = faker.random_int(1, max_subdirectories_count)
        for _ in range(subdirectories_count):
            make_subdirectory_with_content(
                subdir_name=subdir_name / f"{random_string(4)}",
                max_file_count=max_file_count,
            )

    def get_dirs_and_subdris_in_path(path_to_scan: Path) -> list[Path]:
        return [path for path in path_to_scan.rglob("*") if path.is_dir()]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        data_container = ensure_dir(temp_dir_path / "study_data")

        make_subdirectories_with_content(
            subdir_name=data_container, max_subdirectories_count=5, max_file_count=5
        )
        make_files_in_dir(dir_path=data_container, file_count=5)

        # creates a good amount of files
        for _ in range(4):
            for subdirectory_path in get_dirs_and_subdris_in_path(data_container):
                make_subdirectories_with_content(
                    subdir_name=subdirectory_path,
                    max_subdirectories_count=3,
                    max_file_count=3,
                )

        yield temp_dir_path


@pytest.fixture
def exclude_patterns_validation_dir(tmp_path: Path, faker: Faker) -> Path:
    """Directory with well known structure"""
    base_dir = tmp_path / "exclude_patterns_validation_dir"
    base_dir.mkdir()
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1").write_text(faker.text())
    (base_dir / "d1" / "f2.txt").write_text(faker.text())
    (base_dir / "d1" / "sd1").mkdir()
    (base_dir / "d1" / "sd1" / "f1").write_text(faker.text())
    (base_dir / "d1" / "sd1" / "f2.txt").write_text(faker.text())

    print("exclude_patterns_validation_dir ---")
    _print_tree(base_dir)
    return base_dir


def __raise_error(*arts, **kwargs) -> None:
    raise ArchiveError("raised as requested")


@pytest.fixture
def zipfile_single_file_extract_worker_raises_error() -> Iterator[None]:
    # NOTE: cannot MagicMock cannot be serialized via pickle used by
    # multiprocessing, also `__raise_error` cannot be defined in the
    # context fo this function or it cannot be pickled

    # pylint: disable=protected-access
    old_func = archiving_utils._zipfile_single_file_extract_worker
    archiving_utils._zipfile_single_file_extract_worker = __raise_error
    yield
    archiving_utils._zipfile_single_file_extract_worker = old_func


# UTILS


def strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    # NOTE: could use os.path.relpath instead or Path.relative_to ?
    return Path(str(input_path).replace(str(to_strip) + "/", ""))


def get_all_files_in_dir(dir_path: Path) -> set[Path]:
    return {
        strip_directory_from_path(x, dir_path)
        for x in dir_path.rglob("*")
        if x.is_file()
    }


def _compute_hash(file_path: Path) -> tuple[Path, str]:
    with open(file_path, "rb") as file_to_hash:
        file_hash = hashlib.md5()
        chunk = file_to_hash.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = file_to_hash.read(8192)

    return file_path, file_hash.hexdigest()


async def compute_hashes(file_paths: list[Path]) -> dict[Path, str]:
    """given a list of files computes hashes for the files on a process pool"""

    loop = asyncio.get_event_loop()

    with ProcessPoolExecutor() as prcess_pool_executor:
        tasks = [
            loop.run_in_executor(prcess_pool_executor, _compute_hash, file_path)
            for file_path in file_paths
        ]
        # pylint: disable=unnecessary-comprehension
        # see return value of _compute_hash it is a tuple, mapping list[Tuple[Path,str]] to Dict[Path, str] here
        return {k: v for k, v in await asyncio.gather(*tasks)}


def full_file_path_from_dir_and_subdirs(dir_path: Path) -> list[Path]:
    return [x for x in dir_path.rglob("*") if x.is_file()]


def _escape_undecodable_str(s: str) -> str:
    return s.encode(errors="replace").decode("utf-8")


def _escape_undecodable_path(path: Path) -> Path:
    return Path(_escape_undecodable_str(str(path)))


async def assert_same_directory_content(
    dir_to_compress: Path,
    output_dir: Path,
    inject_relative_path: Path | None = None,
    unsupported_replace: bool = False,
) -> None:
    def _relative_path(input_path: Path) -> Path:
        assert inject_relative_path is not None
        return Path(str(inject_relative_path / str(input_path))[1:])

    input_set = get_all_files_in_dir(dir_to_compress)
    output_set = get_all_files_in_dir(output_dir)

    if unsupported_replace:
        input_set = {_escape_undecodable_path(x) for x in input_set}

    if inject_relative_path is not None:
        input_set = {_relative_path(x) for x in input_set}

    assert (
        input_set == output_set
    ), f"There following files are missing {input_set - output_set}"

    # computing the hashes for dir_to_compress and map in a dict
    # with the name starting from the root of the directory and md5sum
    dir_to_compress_hashes = {
        strip_directory_from_path(k, dir_to_compress): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(dir_to_compress))
        ).items()
    }
    dir_to_compress_hashes = {
        _escape_undecodable_path(k): v for k, v in dir_to_compress_hashes.items()
    }

    # computing the hashes for output_dir and map in a dict
    # with the name starting from the root of the directory and md5sum
    output_dir_hashes = {
        strip_directory_from_path(k, output_dir): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(output_dir))
        ).items()
    }

    # finally check if hashes are mapped 1 to 1 in order to verify
    # that the compress/decompress worked correctly
    for key in dir_to_compress_hashes:
        assert (
            dir_to_compress_hashes[key]
            == output_dir_hashes[_relative_path(key) if inject_relative_path else key]
        )


def assert_unarchived_paths(
    unarchived_paths: set[Path],
    src_dir: Path,
    dst_dir: Path,
    is_saved_as_relpath: bool,
    unsupported_replace: bool = False,
):
    is_file_or_emptydir = lambda p: p.is_file() or (p.is_dir() and not any(p.glob("*")))

    # all unarchivedare under dst_dir
    assert all(dst_dir in f.parents for f in unarchived_paths)

    # can be also checked with strings
    assert all(str(f).startswith(str(dst_dir)) for f in unarchived_paths)

    # trim basedir and compare relative paths (alias 'tails') against src_dir
    basedir = str(dst_dir)
    if not is_saved_as_relpath:
        basedir += str(src_dir)

    got_tails = {os.path.relpath(f, basedir) for f in unarchived_paths}
    expected_tails = {
        os.path.relpath(f, src_dir)
        for f in src_dir.rglob("*")
        if is_file_or_emptydir(f)
    }
    if unsupported_replace:
        expected_tails = {_escape_undecodable_str(x) for x in expected_tails}
    assert got_tails == expected_tails


@pytest.mark.skip(reason="DEV:only for manual tessting")
async def test_archiving_utils_against_sample(
    osparc_simcore_root_dir: Path, tmp_path: Path
):
    """
    ONLY for manual testing
    User MUST provide a sample of a zip file in ``sample_path``
    """
    sample_path = osparc_simcore_root_dir / "keep.ignore" / "workspace.zip"
    destination = tmp_path / "unzipped"

    extracted_paths = await unarchive_dir(sample_path, destination)
    assert extracted_paths

    for p in extracted_paths:
        assert isinstance(p, Path), p

    await archive_dir(
        dir_to_compress=destination,
        destination=tmp_path / "test_it.zip",
        compress=True,
        store_relative_path=True,
    )


@pytest.mark.parametrize(
    "compress,store_relative_path",
    itertools.product([True, False], repeat=2),
)
async def test_archive_unarchive_same_structure_dir(
    dir_with_random_content: Path,
    tmp_path: Path,
    compress: bool,
    store_relative_path: bool,
):
    temp_dir_one = tmp_path / "one"
    temp_dir_two = tmp_path / "two"

    temp_dir_one.mkdir()
    temp_dir_two.mkdir()

    archive_file = temp_dir_one / "archive.zip"

    await archive_dir(
        dir_to_compress=dir_with_random_content,
        destination=archive_file,
        store_relative_path=store_relative_path,
        compress=compress,
    )

    unarchived_paths: set[Path] = await unarchive_dir(
        archive_to_extract=archive_file, destination_folder=temp_dir_two
    )

    assert_unarchived_paths(
        unarchived_paths,
        src_dir=dir_with_random_content,
        dst_dir=temp_dir_two,
        is_saved_as_relpath=store_relative_path,
    )

    await assert_same_directory_content(
        dir_with_random_content,
        temp_dir_two,
        None if store_relative_path else dir_with_random_content,
    )


@pytest.mark.parametrize(
    "compress,store_relative_path",
    itertools.product([True, False], repeat=2),
)
async def test_unarchive_in_same_dir_as_archive(
    dir_with_random_content: Path,
    tmp_path: Path,
    compress: bool,
    store_relative_path: bool,
):
    archive_file = tmp_path / "archive.zip"

    await archive_dir(
        dir_to_compress=dir_with_random_content,
        destination=archive_file,
        store_relative_path=store_relative_path,
        compress=compress,
    )

    unarchived_paths = await unarchive_dir(
        archive_to_extract=archive_file, destination_folder=tmp_path
    )

    archive_file.unlink()  # delete before comparing contents

    assert_unarchived_paths(
        unarchived_paths,
        src_dir=dir_with_random_content,
        dst_dir=tmp_path,
        is_saved_as_relpath=store_relative_path,
    )

    await assert_same_directory_content(
        dir_with_random_content,
        tmp_path,
        None if store_relative_path else dir_with_random_content,
    )


@pytest.mark.parametrize(
    "compress,store_relative_path",
    itertools.product([True, False], repeat=2),
)
async def test_regression_unsupported_characters(
    tmp_path: Path,
    compress: bool,
    store_relative_path: bool,
) -> None:
    archive_path = tmp_path / "archive.zip"
    dir_to_archive = tmp_path / "to_compress"
    dir_to_archive.mkdir()
    dst_dir = tmp_path / "decompressed"
    dst_dir.mkdir()

    def _create_file(file_name: str, content: str) -> None:
        file_path = dir_to_archive / file_name
        file_path.write_text(content)
        assert file_path.read_text() == content

    # unsupported file name
    _create_file("something\udce6likethis.txt", "payload1")
    # supported name
    _create_file("this_file_name_works.txt", "payload2")

    await archive_dir(
        dir_to_compress=dir_to_archive,
        destination=archive_path,
        store_relative_path=store_relative_path,
        compress=compress,
    )

    unarchived_paths = await unarchive_dir(
        archive_to_extract=archive_path, destination_folder=dst_dir
    )

    assert_unarchived_paths(
        unarchived_paths,
        src_dir=dir_to_archive,
        dst_dir=dst_dir,
        is_saved_as_relpath=store_relative_path,
        unsupported_replace=True,
    )

    await assert_same_directory_content(
        dir_to_compress=dir_to_archive,
        output_dir=dst_dir,
        inject_relative_path=None if store_relative_path else dir_to_archive,
        unsupported_replace=True,
    )


EMPTY_SET: set[Path] = set()
ALL_ITEMS_SET: set[Path] = {
    Path("d1/f2.txt"),
    Path("d1/f1"),
    Path("d1/sd1/f1"),
    Path("d1/sd1/f2.txt"),
}


@dataclass(frozen=True)
class ExcludeParams:
    exclude_patterns: set[str]
    expected_result: set[Path]


# + /exclude_patterns_validation_dir
#  + empty
#  + d1
#   - f2.txt
#   + sd1
#    - f2.txt
#    - f1
#   - f1
@pytest.mark.parametrize(
    "params",
    [
        ExcludeParams(
            exclude_patterns={"/d1*"},
            expected_result=EMPTY_SET,
        ),
        ExcludeParams(
            exclude_patterns={"/d1/sd1*"},
            expected_result={
                Path("d1/f2.txt"),
                Path("d1/f1"),
            },
        ),
        ExcludeParams(
            exclude_patterns={"d1*"},
            expected_result=EMPTY_SET,
        ),
        ExcludeParams(
            exclude_patterns={"*d1*"},
            expected_result=EMPTY_SET,
        ),
        ExcludeParams(
            exclude_patterns={"*.txt"},
            expected_result={
                Path("d1/f1"),
                Path("d1/sd1/f1"),
            },
        ),
        ExcludeParams(
            exclude_patterns={"/absolute/path/does/not/exist*"},
            expected_result=ALL_ITEMS_SET,
        ),
        ExcludeParams(
            exclude_patterns={"/../../this/is/ignored*"},
            expected_result=ALL_ITEMS_SET,
        ),
        ExcludeParams(
            exclude_patterns={"*relative/path/does/not/exist"},
            expected_result=ALL_ITEMS_SET,
        ),
    ],
)
async def test_archive_unarchive_check_exclude(
    params: ExcludeParams,
    exclude_patterns_validation_dir: Path,
    tmp_path: Path,
):
    temp_dir_one = tmp_path / "one"
    temp_dir_two = tmp_path / "two"

    temp_dir_one.mkdir()
    temp_dir_two.mkdir()

    archive_file = temp_dir_one / "archive.zip"

    # make exclude_patterns work relative to test directory
    exclude_patterns = {
        f"{exclude_patterns_validation_dir}/{x.strip('/') if x.startswith('/') else x}"
        for x in params.exclude_patterns
    }

    await archive_dir(
        dir_to_compress=exclude_patterns_validation_dir,
        destination=archive_file,
        store_relative_path=True,
        compress=False,
        exclude_patterns=exclude_patterns,
    )

    unarchived_paths: set[Path] = await unarchive_dir(
        archive_to_extract=archive_file, destination_folder=temp_dir_two
    )

    relative_unarchived_paths = {x.relative_to(temp_dir_two) for x in unarchived_paths}

    assert (
        relative_unarchived_paths == params.expected_result
    ), f"Exclude rules: {exclude_patterns=}"


async def test_unarchive_dir_raises_error(
    zipfile_single_file_extract_worker_raises_error: None,
    dir_with_random_content: Path,
    tmp_path: Path,
):
    temp_dir_one = tmp_path / "one"
    temp_dir_two = tmp_path / "two"

    temp_dir_one.mkdir()
    temp_dir_two.mkdir()

    archive_file = temp_dir_one / "archive.zip"

    await archive_dir(
        dir_to_compress=dir_with_random_content,
        destination=archive_file,
        store_relative_path=True,
        compress=True,
    )

    with pytest.raises(ArchiveError, match=r"^.*raised as requested.*$"):
        await archiving_utils.unarchive_dir(archive_file, temp_dir_two)


file_suffix = 0


async def _archive_dir_performance(
    input_path: Path, destination_path: Path, compress: bool
):
    global file_suffix  # pylint: disable=global-statement

    await archive_dir(
        input_path,
        destination_path / f"archive_{file_suffix}.zip",
        compress=compress,
        store_relative_path=True,
    )
    file_suffix += 1


@pytest.mark.skip(reason="manual testing")
@pytest.mark.parametrize(
    "compress, file_size, num_files",
    [(False, TypeAdapter(ByteSize).validate_python("1Mib"), 10000)],
)
def test_archive_dir_performance(
    benchmark: BenchmarkFixture,
    create_file_of_size: Callable[[ByteSize, str], Path],
    tmp_path: Path,
    compress: bool,
    file_size: ByteSize,
    num_files: int,
):
    # create a bunch of different files
    files_to_compress = [
        create_file_of_size(file_size, f"inputs/test_file_{n}")
        for n in range(num_files)
    ]
    assert len(files_to_compress) == num_files
    parent_path = files_to_compress[0].parent
    assert all(f.parent == parent_path for f in files_to_compress)

    destination_path = tmp_path / "archive_performance"
    assert not destination_path.exists()
    destination_path.mkdir(parents=True)
    assert destination_path.exists()

    def run_async_test(*args, **kwargs):
        asyncio.get_event_loop().run_until_complete(
            _archive_dir_performance(parent_path, destination_path, compress)
        )

    benchmark(run_async_test)


def _touch_all_files_in_path(path_to_archive: Path) -> None:
    for path in path_to_archive.rglob("*"):
        print("touching", path)
        path.touch()


@pytest.fixture
async def mixed_file_types(tmp_path: Path, faker: Faker) -> AsyncIterable[Path]:
    base_dir = tmp_path / "mixed_types_dir"
    base_dir.mkdir()

    # mixed small text files and binary files
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1.txt").write_text(faker.text())
    (base_dir / "d1" / "b2.bin").write_bytes(faker.json_bytes())
    (base_dir / "d1" / "sd1").mkdir()
    (base_dir / "d1" / "sd1" / "f1.txt").write_text(faker.text())
    (base_dir / "d1" / "sd1" / "b2.bin").write_bytes(faker.json_bytes())
    (base_dir / "images").mkdir()

    # images cause issues with zipping, below content produced different
    # hashes for zip files
    for i in range(2):
        image_dir = base_dir / f"images{i}"
        image_dir.mkdir()
        for n in range(50):
            a = numpy.random.rand(900, 900, 3) * 255  # noqa: NPY002
            im_out = Image.fromarray(a.astype("uint8")).convert("RGB")
            image_path = image_dir / f"out{n}.jpg"
            im_out.save(image_path)

    print("mixed_types_dir ---")
    _print_tree(base_dir)

    yield base_dir

    await remove_directory(base_dir)
    assert not base_dir.exists()


@pytest.mark.parametrize(
    "store_relative_path, compress",
    [
        # test that all possible combinations still work
        pytest.param(False, False, id="no_relative_path_no_compress"),
        pytest.param(False, True, id="no_relative_path_with_compression"),
        pytest.param(True, False, id="nodeports_options"),
        pytest.param(True, True, id="with_relative_path_with_compression"),
    ],
)
async def test_regression_archive_hash_does_not_change(
    mixed_file_types: Path,
    tmp_path: Path,
    store_relative_path: bool,
    compress: bool,
):
    destination_path = tmp_path / "archives_to_compare"
    destination_path.mkdir(parents=True, exist_ok=True)

    first_archive = destination_path / "first"
    second_archive = destination_path / "second"
    assert not first_archive.exists()
    assert not second_archive.exists()
    assert first_archive != second_archive

    await archive_dir(
        mixed_file_types,
        first_archive,
        compress=compress,
        store_relative_path=store_relative_path,
    )

    _touch_all_files_in_path(mixed_file_types)

    await archive_dir(
        mixed_file_types,
        second_archive,
        compress=compress,
        store_relative_path=store_relative_path,
    )

    _, first_hash = _compute_hash(first_archive)
    _, second_hash = _compute_hash(second_archive)
    assert first_hash == second_hash
