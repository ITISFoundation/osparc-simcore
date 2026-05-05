# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio
import contextlib
from unittest import mock

import pytest
from faker import Faker
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from pydantic import ValidationError
from pytest_mock import MockerFixture
from servicelib.progress_bar import (
    _INITIAL_VALUE,
    _MIN_PROGRESS_UPDATE_PERCENT,
    _PROGRESS_ALREADY_REACGED_MAXIMUM,
    ProgressBarData,
)


@pytest.fixture
def mocked_progress_bar_cb(mocker: MockerFixture) -> mock.Mock:
    def _progress_cb(*args, **kwargs) -> None:
        print(f"received progress: {args}, {kwargs}")

    return mocker.Mock(side_effect=_progress_cb)


@pytest.fixture
def async_mocked_progress_bar_cb(mocker: MockerFixture) -> mock.AsyncMock:
    async def _progress_cb(*args, **kwargs) -> None:
        print(f"received progress: {args}, {kwargs}")

    return mocker.AsyncMock(side_effect=_progress_cb)


@pytest.mark.parametrize(
    "progress_report_cb_type",
    ["mocked_progress_bar_cb", "async_mocked_progress_bar_cb"],
)
async def test_progress_bar_progress_report_cb(
    progress_report_cb_type: str,
    mocked_progress_bar_cb: mock.Mock,
    async_mocked_progress_bar_cb: mock.AsyncMock,
    faker: Faker,
):
    mocked_cb: mock.Mock | mock.AsyncMock = {
        "mocked_progress_bar_cb": mocked_progress_bar_cb,
        "async_mocked_progress_bar_cb": async_mocked_progress_bar_cb,
    }[progress_report_cb_type]
    outer_num_steps = 3
    async with ProgressBarData(
        num_steps=outer_num_steps,
        progress_report_cb=mocked_cb,
        progress_unit="Byte",
        description=faker.pystr(),
    ) as root:
        assert root.num_steps == outer_num_steps
        assert root.step_weights is None  # i.e. all steps have equal weight
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        mocked_cb.assert_called_once_with(
            ProgressReport(
                actual_value=0,
                total=outer_num_steps,
                unit="Byte",
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=0.0,
                    total=outer_num_steps,
                    unit="Byte",
                    sub=None,
                ),
            )
        )
        mocked_cb.reset_mock()
        # first step is done right away
        await root.update()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001
        mocked_cb.assert_called_once_with(
            ProgressReport(
                actual_value=1,
                total=outer_num_steps,
                unit="Byte",
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=1.0,
                    total=outer_num_steps,
                    unit="Byte",
                    sub=None,
                ),
            )
        )
        mocked_cb.reset_mock()

        # 2nd step is a sub progress bar of 10 steps
        inner_num_steps_step2 = 100
        async with root.sub_progress(steps=inner_num_steps_step2, description=faker.pystr()) as sub:
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1)  # noqa: SLF001
            for i in range(inner_num_steps_step2):
                await sub.update()
                assert sub._current_steps == pytest.approx(float(i + 1))  # noqa: SLF001
                assert root._current_steps == pytest.approx(  # noqa: SLF001
                    1 + float(i + 1) / float(inner_num_steps_step2)
                )
        assert sub._current_steps == pytest.approx(  # noqa: SLF001
            inner_num_steps_step2
        )
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
        mocked_cb.assert_called()
        assert mocked_cb.call_args_list[-1].args[0].percent_value == pytest.approx(2 / 3)
        for call_index, call in enumerate(mocked_cb.call_args_list[1:-1]):
            assert (
                call.args[0].percent_value - mocked_cb.call_args_list[call_index].args[0].percent_value
            ) > _MIN_PROGRESS_UPDATE_PERCENT

        mocked_cb.reset_mock()

        # 3rd step is another subprogress of 50 steps
        inner_num_steps_step3 = 50
        async with root.sub_progress(steps=inner_num_steps_step3, description=faker.pystr()) as sub:
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(2)  # noqa: SLF001
            for i in range(inner_num_steps_step3):
                await sub.update()
                assert sub._current_steps == pytest.approx(float(i + 1))  # noqa: SLF001
                assert root._current_steps == pytest.approx(  # noqa: SLF001
                    2 + float(i + 1) / float(inner_num_steps_step3)
                )
        assert sub._current_steps == pytest.approx(  # noqa: SLF001
            inner_num_steps_step3
        )
        assert root._current_steps == pytest.approx(3)  # noqa: SLF001
        mocked_cb.assert_called()
        assert mocked_cb.call_args_list[-1].args[0].percent_value == 1.0
        mocked_cb.reset_mock()


def test_creating_progress_bar_with_invalid_unit_fails(faker: Faker):
    with pytest.raises(ValidationError):
        ProgressBarData(num_steps=321, progress_unit="invalid", description=faker.pystr())


async def test_progress_bar_always_reports_0_on_creation_and_1_on_finish(
    mocked_progress_bar_cb: mock.Mock, faker: Faker
):
    num_steps = 156587
    progress_bar = ProgressBarData(
        num_steps=num_steps,
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    )
    assert progress_bar._current_steps == _INITIAL_VALUE  # noqa: SLF001
    async with progress_bar as root:
        assert root is progress_bar
        assert root._current_steps == 0  # noqa: SLF001
        mocked_progress_bar_cb.assert_called_once_with(
            ProgressReport(
                actual_value=0,
                total=num_steps,
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=0.0,
                    total=num_steps,
                    unit=None,
                    sub=None,
                ),
            )
        )

    # going out of scope always updates to final number of steps
    assert progress_bar._current_steps == num_steps  # noqa: SLF001
    assert mocked_progress_bar_cb.call_args_list[-1] == mock.call(
        ProgressReport(
            actual_value=num_steps,
            total=num_steps,
            message=ProgressStructuredMessage(
                description=root.description,
                current=num_steps,
                total=num_steps,
                unit=None,
                sub=None,
            ),
        )
    )


async def test_progress_bar_always_reports_1_on_finish(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    num_steps = 156587
    chunks = 123.3

    num_chunked_steps = int(num_steps / chunks)
    last_step = num_steps % chunks
    progress_bar = ProgressBarData(
        num_steps=num_steps,
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    )
    assert progress_bar._current_steps == _INITIAL_VALUE  # noqa: SLF001
    async with progress_bar as root:
        assert root is progress_bar
        assert root._current_steps == 0  # noqa: SLF001
        mocked_progress_bar_cb.assert_called_once_with(
            ProgressReport(
                actual_value=0,
                total=num_steps,
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=0,
                    total=num_steps,
                    unit=None,
                    sub=None,
                ),
            )
        )
        for _ in range(num_chunked_steps):
            await root.update(chunks)
        await root.update(last_step)
        assert progress_bar._current_steps == pytest.approx(num_steps)  # noqa: SLF001

    # going out of scope always updates to final number of steps
    assert progress_bar._current_steps == pytest.approx(num_steps)  # noqa: SLF001
    assert mocked_progress_bar_cb.call_args_list[-1] == mock.call(
        ProgressReport(
            actual_value=num_steps,
            total=num_steps,
            message=ProgressStructuredMessage(
                description=root.description,
                current=num_steps,
                total=num_steps,
                unit=None,
                sub=None,
            ),
        )
    )


async def test_set_progress(caplog: pytest.LogCaptureFixture, faker: Faker):
    async with ProgressBarData(num_steps=50, description=faker.pystr()) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.num_steps == 50
        assert root.step_weights is None
        await root.set_(13)
        assert root._current_steps == pytest.approx(13)  # noqa: SLF001
        await root.set_(34)
        assert root._current_steps == pytest.approx(34)  # noqa: SLF001
        await root.set_(58)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "WARNING" in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_reset_progress(caplog: pytest.LogCaptureFixture, faker: Faker):
    async with ProgressBarData(num_steps=50, description=faker.pystr()) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.num_steps == 50
        assert root.step_weights is None
        await root.set_(50)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "WARNING" not in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM not in caplog.text
        await root.set_(51)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "WARNING" in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM in caplog.text

        caplog.clear()
        root.reset()

        assert root._current_steps == pytest.approx(-1)  # noqa: SLF001
        assert "WARNING" not in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM not in caplog.text

        await root.set_(12)
        assert root._current_steps == pytest.approx(12)  # noqa: SLF001
        assert "WARNING" not in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM not in caplog.text

        await root.set_(51)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "WARNING" in caplog.text
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM in caplog.text


async def test_concurrent_progress_bar(faker: Faker):
    async def do_something(root: ProgressBarData):
        async with root.sub_progress(steps=50, description=faker.pystr()) as sub:
            assert sub.num_steps == 50
            assert sub.step_weights is None
            assert sub._current_steps == 0  # noqa: SLF001
            for n in range(50):
                await sub.update()
                assert sub._current_steps == (n + 1)  # noqa: SLF001

    async with ProgressBarData(num_steps=12, description=faker.pystr()) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.step_weights is None
        await asyncio.gather(*[do_something(root) for n in range(12)])
        assert root._current_steps == pytest.approx(12)  # noqa: SLF001


async def test_too_many_sub_progress_bars_raises(faker: Faker):
    async with ProgressBarData(num_steps=2, description=faker.pystr()) as root:
        assert root.num_steps == 2
        assert root.step_weights is None
        async with root.sub_progress(steps=50, description=faker.pystr()) as sub:
            for _ in range(50):
                await sub.update()
            async with root.sub_progress(steps=50, description=faker.pystr()) as sub2:
                for _ in range(50):
                    await sub2.update()
                with pytest.raises(RuntimeError):
                    root.sub_progress(steps=50, description=faker.pystr())


async def test_too_many_updates_does_not_raise_but_show_warning_with_stack(
    caplog: pytest.LogCaptureFixture, faker: Faker
):
    async with ProgressBarData(num_steps=2, description=faker.pystr()) as root:
        assert root.num_steps == 2
        assert root.step_weights is None
        await root.update()
        await root.update()
        await root.update()
        assert _PROGRESS_ALREADY_REACGED_MAXIMUM in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_weighted_progress_bar(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    outer_num_steps = 3
    async with ProgressBarData(
        num_steps=outer_num_steps,
        step_weights=[1, 3, 1],
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        mocked_progress_bar_cb.assert_called_once_with(
            ProgressReport(
                actual_value=0,
                total=outer_num_steps,
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=0,
                    total=outer_num_steps,
                    unit=None,
                    sub=None,
                ),
            )
        )
        mocked_progress_bar_cb.reset_mock()
        assert root.step_weights == [1 / 5, 3 / 5, 1 / 5, 0]
        await root.update()
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(1 / 5)
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001
        await root.update()
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(1 / 5 + 3 / 5)
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001

    mocked_progress_bar_cb.assert_called_once_with(
        ProgressReport(
            actual_value=outer_num_steps,
            total=outer_num_steps,
            message=ProgressStructuredMessage(
                description=root.description,
                current=outer_num_steps,
                total=outer_num_steps,
                unit=None,
                sub=None,
            ),
        )
    )
    mocked_progress_bar_cb.reset_mock()
    assert root._current_steps == pytest.approx(3)  # noqa: SLF001


async def test_weighted_progress_bar_with_weighted_sub_progress(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    outer_num_steps = 3
    async with ProgressBarData(
        num_steps=outer_num_steps,
        step_weights=[1, 3, 1],
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        mocked_progress_bar_cb.assert_called_once_with(
            ProgressReport(
                actual_value=0,
                total=outer_num_steps,
                message=ProgressStructuredMessage(
                    description=root.description,
                    current=0,
                    total=outer_num_steps,
                    unit=None,
                    sub=None,
                ),
            )
        )
        mocked_progress_bar_cb.reset_mock()
        assert root.step_weights == [1 / 5, 3 / 5, 1 / 5, 0]
        # first step
        await root.update()
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(1 / 5)
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # 2nd step is a sub progress bar of 5 steps
        async with root.sub_progress(steps=5, step_weights=[2, 5, 1, 2, 3], description=faker.pystr()) as sub:
            assert sub.step_weights == [2 / 13, 5 / 13, 1 / 13, 2 / 13, 3 / 13, 0]
            assert sub._current_steps == pytest.approx(0)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1)  # noqa: SLF001
            # sub steps
            # 1
            await sub.update()
            assert sub._current_steps == pytest.approx(1)  # noqa: SLF001
            assert root._current_steps == pytest.approx(1 + 2 / 13)  # noqa: SLF001
            # 2
            await sub.update()
            assert sub._current_steps == pytest.approx(2)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13
            )
            # 3
            await sub.update()
            assert sub._current_steps == pytest.approx(3)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13 + 1 / 13
            )
            # 4
            await sub.update()
            assert sub._current_steps == pytest.approx(4)  # noqa: SLF001
            assert root._current_steps == pytest.approx(  # noqa: SLF001
                1 + 2 / 13 + 5 / 13 + 1 / 13 + 2 / 13
            )
            # 5
            await sub.update()
            assert sub._current_steps == pytest.approx(5)  # noqa: SLF001
            assert root._current_steps == pytest.approx(2)  # noqa: SLF001

        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
        mocked_progress_bar_cb.assert_called()
        assert mocked_progress_bar_cb.call_count == 5
        assert mocked_progress_bar_cb.call_args_list[4].args[0].percent_value == pytest.approx(1 / 5 + 3 / 5)
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001
    mocked_progress_bar_cb.assert_called_once_with(
        ProgressReport(
            actual_value=outer_num_steps,
            total=outer_num_steps,
            message=ProgressStructuredMessage(
                description=root.description,
                current=outer_num_steps,
                total=outer_num_steps,
                unit=None,
                sub=None,
            ),
        )
    )
    mocked_progress_bar_cb.reset_mock()
    assert root._current_steps == pytest.approx(3)  # noqa: SLF001


async def test_weighted_progress_bar_wrong_num_weights_raises(faker: Faker):
    with pytest.raises(RuntimeError):
        async with ProgressBarData(num_steps=3, step_weights=[3, 1], description=faker.pystr()):
            ...


async def test_weighted_progress_bar_with_0_weights_is_equivalent_to_standard_progress_bar(
    faker: Faker,
):
    async with ProgressBarData(num_steps=3, step_weights=[0, 0, 0], description=faker.pystr()) as root:
        assert root.step_weights == [1, 1, 1, 0]


@pytest.mark.xfail(reason="show how to not use the progress bar")
async def test_concurrent_sub_progress_update_correct_sub_progress(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    async with ProgressBarData(
        num_steps=3,
        step_weights=[3, 1, 2],
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        sub_progress1 = root.sub_progress(23, description=faker.pystr())
        assert sub_progress1._current_steps == _INITIAL_VALUE  # noqa: SLF001
        sub_progress2 = root.sub_progress(45, description=faker.pystr())
        assert sub_progress2._current_steps == _INITIAL_VALUE  # noqa: SLF001
        sub_progress3 = root.sub_progress(12, description=faker.pystr())
        assert sub_progress3._current_steps == _INITIAL_VALUE  # noqa: SLF001

        # NOTE: in a gather call there is no control on which step finishes first

        assert root._current_steps == 0  # noqa: SLF001
        # complete last progress
        async with sub_progress3:
            ...
        # so sub 3 is done here
        assert sub_progress3._current_steps == 12  # noqa: SLF001
        assert mocked_progress_bar_cb.call_count == 2
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(2 / 6)


# -------------------------------------------------------------------
# Tests for sub_progress child cleanup on __aexit__ (retry support)
# -------------------------------------------------------------------


async def test_sub_progress_child_removed_from_parent_on_exit(faker: Faker):
    """After a sub_progress context manager exits, the child should be
    removed from the parent's _children list so a new sub_progress can
    be created for the same step (e.g. on retry)."""
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as root:
        async with root.sub_progress(steps=10, description=faker.pystr()) as sub:
            for _ in range(10):
                await sub.update()
        assert len(root._children) == 0  # noqa: SLF001


async def test_sub_progress_retry_creates_new_child_after_error_exit(faker: Faker):
    """Simulates a retry scenario: first sub_progress exits via exception,
    then a new sub_progress is created on the same parent with num_steps=1.
    This should succeed (not raise RuntimeError)."""
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as root:
        # First attempt — fails with an exception after partial progress
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=100, description="attempt 1") as sub:
                for _ in range(50):
                    await sub.update()
                msg = "simulated upload failure"
                raise RuntimeError(msg)
        # Second attempt (retry) — must NOT raise RuntimeError
        async with root.sub_progress(steps=100, description="attempt 2") as sub:
            for _ in range(100):
                await sub.update()


async def test_sub_progress_parent_progress_decremented_on_error_exit(faker: Faker):
    """When a child exits via exception, the parent's _current_steps
    should be rolled back so a retry doesn't over-count progress."""
    async with ProgressBarData(num_steps=2, description=faker.pystr()) as root:
        await root.update()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # First attempt via sub_progress — fails with exception
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=10, description="attempt 1") as sub:
                for _ in range(5):
                    await sub.update()
                msg = "simulated failure"
                raise RuntimeError(msg)
        # Child exited via exception — parent progress rolled back
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # Retry creates a new child for the same step
        async with root.sub_progress(steps=10, description="attempt 2") as sub:
            for _ in range(10):
                await sub.update()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001


async def test_sub_progress_retry_reports_correct_progress(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    """Verify that after an error + retry, the progress callback:
    1. Does NOT emit a spurious 100% from the failed attempt
    2. Emits intermediate reports from near 0% during the retry
    3. Ends at 1.0"""
    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        mocked_progress_bar_cb.reset_mock()

        # First attempt — partial progress then error exit
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=100, description="attempt 1") as sub:
                for _ in range(50):
                    await sub.update()
                msg = "simulated failure"
                raise RuntimeError(msg)

        # The failed attempt must NOT emit a spurious 1.0 (100%) report
        reports_after_error = [call.args[0] for call in mocked_progress_bar_cb.call_args_list]
        assert all(r.percent_value < 1.0 for r in reports_after_error), (
            "Error exit emitted a spurious 100% report before rollback"
        )

        mocked_progress_bar_cb.reset_mock()

        # Second attempt — completes fully
        async with root.sub_progress(steps=100, description="attempt 2") as sub:
            for _ in range(100):
                await sub.update()

    # Retry reports must include intermediates starting near 0%
    retry_reports = [call.args[0] for call in mocked_progress_bar_cb.call_args_list]
    intermediate_reports = [r for r in retry_reports if r.percent_value < 1.0]
    assert len(intermediate_reports) > 0, "No intermediate progress reports emitted during retry"
    first_retry_report = intermediate_reports[0]
    assert first_retry_report.percent_value < 0.1, (
        f"First retry report at {first_retry_report.percent_value:.0%} — "
        "expected near 0%; _last_report_value was not reset after rollback"
    )
    # Retry must end at 1.0
    last_report: ProgressReport = retry_reports[-1]
    assert last_report.percent_value == pytest.approx(1.0)


async def test_sub_progress_retry_with_weighted_parent(mocked_progress_bar_cb: mock.Mock, faker: Faker):
    """Retry on a weighted parent must correctly rollback and re-report
    progress using weighted _compute_progress (not just steps/num_steps)."""
    async with ProgressBarData(
        num_steps=2,
        step_weights=[3, 1],
        progress_report_cb=mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        # First step (weight=3/4 of total) — fails after partial progress
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=100, description="attempt 1") as sub:
                for _ in range(50):
                    await sub.update()
                msg = "simulated failure"
                raise RuntimeError(msg)

        # Parent progress should be rolled back to 0
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001

        mocked_progress_bar_cb.reset_mock()

        # Retry the first step — completes fully
        async with root.sub_progress(steps=100, description="attempt 2") as sub:
            for _ in range(100):
                await sub.update()

        # Parent should have advanced by the first step's weight (3/4)
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # Reports during retry should start near 0%, not at 37.5% (half of 3/4)
        retry_reports = [call.args[0] for call in mocked_progress_bar_cb.call_args_list]
        intermediate_reports = [r for r in retry_reports if r.percent_value < 0.75]
        assert len(intermediate_reports) > 0
        first_retry_report = intermediate_reports[0]
        assert first_retry_report.percent_value < 0.1, (
            f"First retry report at {first_retry_report.percent_value:.0%} — "
            "weighted rollback did not reset report baseline"
        )


async def test_sub_progress_multiple_sequential_reuse(faker: Faker):
    """Create and exit more sub_progress children than num_steps,
    but sequentially (one at a time). Should succeed after fix."""
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as root:
        for i in range(5):
            async with root.sub_progress(steps=10, description=f"attempt {i}") as sub:
                for _ in range(10):
                    await sub.update()
        assert len(root._children) == 0  # noqa: SLF001


async def test_sub_progress_deeply_nested_retry_emits_intermediate_reports(
    mocked_progress_bar_cb: mock.Mock, faker: Faker
):
    """In a root -> mid -> leaf nesting, when the leaf fails and retries,
    intermediate reports must be emitted at the root level (not suppressed
    because an ancestor's _last_report_value was left at the old high-water mark)."""
    async with (
        ProgressBarData(
            num_steps=1,
            progress_report_cb=mocked_progress_bar_cb,
            description=faker.pystr(),
        ) as root,
        root.sub_progress(steps=1, description="mid") as mid,
    ):
        # First attempt at leaf — fails after partial progress
        with contextlib.suppress(RuntimeError):
            async with mid.sub_progress(steps=100, description="leaf attempt 1") as leaf:
                for _ in range(50):
                    await leaf.update()
                msg = "simulated failure"
                raise RuntimeError(msg)

        mocked_progress_bar_cb.reset_mock()

        # Retry leaf — should emit intermediate reports from near 0%
        async with mid.sub_progress(steps=100, description="leaf attempt 2") as leaf:
            for _ in range(100):
                await leaf.update()

    retry_reports = [call.args[0] for call in mocked_progress_bar_cb.call_args_list]
    intermediate_reports = [r for r in retry_reports if r.percent_value < 1.0]
    assert len(intermediate_reports) > 0, "No intermediate reports during deeply nested retry"
    first_retry_report = intermediate_reports[0]
    assert first_retry_report.percent_value < 0.1, (
        f"First retry report at {first_retry_report.percent_value:.0%} — "
        "ancestor _last_report_value was not reset after rollback"
    )


async def test_sub_progress_cancellation_rolls_back_and_allows_same_slot_retry(
    mocked_progress_bar_cb: mock.Mock,
):
    """CancelledError must rollback partial progress and remove the child,
    so a caller that catches CancelledError and retries the same sub-step
    does not over-count parent progress."""
    async with ProgressBarData(
        num_steps=1,
        description="root",
        progress_report_cb=mocked_progress_bar_cb,
    ) as root:
        # Child makes partial progress then gets cancelled
        with pytest.raises(asyncio.CancelledError):  # noqa: PT012
            async with root.sub_progress(steps=10, description="cancelled-child") as child:
                await child.update(5)  # 50% of child = 0.5 parent steps
                raise asyncio.CancelledError

        # Child removed and parent progress rolled back to 0
        assert len(root._children) == 0  # noqa: SLF001
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001

        # Retry on the same slot — completes fully
        async with root.sub_progress(steps=10, description="retry-child") as child:
            for _ in range(10):
                await child.update()

    # Ends at exactly 1.0, not 1.5 (which would happen without rollback)
    final_report = mocked_progress_bar_cb.call_args_list[-1].args[0]
    assert final_report.percent_value == pytest.approx(1.0)


async def test_sub_progress_real_task_cancellation_removes_child_and_rolls_back():
    """Verify cleanup works with real task cancellation via task.cancel(),
    not just a manually raised CancelledError."""

    async def _worker(root: ProgressBarData) -> None:
        async with root.sub_progress(steps=100, description="worker") as child:
            for _ in range(50):
                await child.update()
            # Simulate a long await where cancellation arrives
            await asyncio.sleep(10)

    async with ProgressBarData(num_steps=1, description="root") as root:
        task = asyncio.create_task(_worker(root))
        # Let the worker make progress
        await asyncio.sleep(0)
        # Cancel the task for real
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Child must have been removed and progress rolled back
        assert len(root._children) == 0  # noqa: SLF001
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001

        # Same slot is reusable
        async with root.sub_progress(steps=100, description="retry") as child:
            for _ in range(100):
                await child.update()

    assert root._current_steps == pytest.approx(1)  # noqa: SLF001


async def test_sub_progress_nested_exception_does_not_double_rollback():
    """When root -> mid -> leaf and leaf raises, the exception propagates
    through both mid and leaf __aexit__. Verify that root's steps completed
    BEFORE mid are preserved (no double subtraction)."""
    async with ProgressBarData(num_steps=3, description="root") as root:
        # Complete first step manually
        await root.update()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # Second step via nested sub_progress that fails
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=1, description="mid") as mid:
                async with mid.sub_progress(steps=100, description="leaf") as leaf:
                    for _ in range(50):
                        await leaf.update()
                    msg = "boom"
                    raise RuntimeError(msg)

        # Root should be at exactly 1 — the first manual step is preserved,
        # mid's partial contribution (from leaf) is fully rolled back.
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # Third step works normally
        await root.update()
        assert root._current_steps == pytest.approx(2)  # noqa: SLF001


async def test_sub_progress_retry_with_async_callback(async_mocked_progress_bar_cb: mock.AsyncMock, faker: Faker):
    """Exercise the retry/rollback path with an async progress_report_cb
    to ensure awaitable callbacks don't break rollback or report behavior."""
    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=async_mocked_progress_bar_cb,
        description=faker.pystr(),
    ) as root:
        async_mocked_progress_bar_cb.reset_mock()

        # First attempt — partial progress then error
        with contextlib.suppress(RuntimeError):
            async with root.sub_progress(steps=100, description="attempt 1") as sub:
                for _ in range(50):
                    await sub.update()
                msg = "simulated failure"
                raise RuntimeError(msg)

        # No spurious 100% report
        reports_after_error = [call.args[0] for call in async_mocked_progress_bar_cb.call_args_list]
        assert all(r.percent_value < 1.0 for r in reports_after_error)

        async_mocked_progress_bar_cb.reset_mock()

        # Retry — completes fully
        async with root.sub_progress(steps=100, description="attempt 2") as sub:
            for _ in range(100):
                await sub.update()

    # Retry reports include intermediates near 0% and end at 1.0
    retry_reports = [call.args[0] for call in async_mocked_progress_bar_cb.call_args_list]
    assert retry_reports[-1].percent_value == pytest.approx(1.0)
    intermediate_reports = [r for r in retry_reports if r.percent_value < 1.0]
    assert len(intermediate_reports) > 0
    assert intermediate_reports[0].percent_value < 0.1
