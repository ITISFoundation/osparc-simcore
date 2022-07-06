# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import Iterable
from servicelib.fastapi.long_running import mark_long_running_task, _decorators, _models
import pytest

# FIXTURES


@pytest.fixture
def mock_markers() -> Iterable[None]:
    original = _decorators.MARKED_FUNCTIONS
    _decorators.MARKED_FUNCTIONS = {}
    yield
    _decorators.MARKED_FUNCTIONS = original


# TESTS


async def test_mark_ok(mock_markers: None) -> None:
    @mark_long_running_task()
    async def background_task_1(progress) -> None:
        ...

    assert len(_decorators.MARKED_FUNCTIONS) == 1

    @mark_long_running_task()
    async def background_task_2(progress) -> None:
        ...

    assert len(_decorators.MARKED_FUNCTIONS) == 2


async def test_adding_function_twice(mock_markers: None) -> None:
    def first_context():
        @mark_long_running_task()
        async def background_task_1(progress) -> None:
            ...

        assert len(_decorators.MARKED_FUNCTIONS) == 1

    def second_context():
        with pytest.raises(ValueError) as exe_info:

            @mark_long_running_task()
            async def background_task_1(progress) -> None:
                ...

        assert (
            exe_info.value.args[0]
            == "A function named 'background_task_1' was already added"
        )

    first_context()
    second_context()


async def test_missing_progress_argument(mock_markers: None) -> None:
    with pytest.raises(ValueError) as exe_info:

        @mark_long_running_task()
        async def a_background_task() -> None:
            ...

    assert (
        exe_info.value.args[0]
        == "Function 'a_background_task' must define at least 1 positional argument used for the progress"
    )
    assert len(_decorators.MARKED_FUNCTIONS) == 0

    with pytest.raises(ValueError) as exe_info:

        @mark_long_running_task()
        async def another_background_task(var="with_value") -> None:
            ...

    assert (
        exe_info.value.args[0]
        == "Function 'another_background_task' must define at least 1 positional argument used for the progress"
    )
    assert len(_decorators.MARKED_FUNCTIONS) == 0


@pytest.mark.parametrize("unique", [True, False])
async def test_mark_options(mock_markers: None, unique: bool) -> None:
    @mark_long_running_task(unique=unique)
    async def background_task_1(progress) -> None:
        ...

    assert len(_decorators.MARKED_FUNCTIONS) == 1
    entry = list(_decorators.MARKED_FUNCTIONS.values())[0]
    _, mark_options = entry
    assert isinstance(mark_options, _models.MarkOptions)
    assert mark_options.unique == unique
