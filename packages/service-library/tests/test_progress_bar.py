# pylint: disable=broad-except
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

import asyncio
from unittest import mock

import pytest
from faker import Faker
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from pydantic import ValidationError
from pytest_mock import MockerFixture
from servicelib.progress_bar import (
    _INITIAL_VALUE,
    _MIN_PROGRESS_UPDATE_PERCENT,
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
        async with root.sub_progress(
            steps=inner_num_steps_step2, description=faker.pystr()
        ) as sub:
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
        assert mocked_cb.call_args_list[-1].args[0].percent_value == pytest.approx(
            2 / 3
        )
        for call_index, call in enumerate(mocked_cb.call_args_list[1:-1]):
            assert (
                call.args[0].percent_value
                - mocked_cb.call_args_list[call_index].args[0].percent_value
            ) > _MIN_PROGRESS_UPDATE_PERCENT

        mocked_cb.reset_mock()

        # 3rd step is another subprogress of 50 steps
        inner_num_steps_step3 = 50
        async with root.sub_progress(
            steps=inner_num_steps_step3, description=faker.pystr()
        ) as sub:
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
        ProgressBarData(
            num_steps=321, progress_unit="invalid", description=faker.pystr()
        )


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


async def test_progress_bar_always_reports_1_on_finish(
    mocked_progress_bar_cb: mock.Mock, faker: Faker
):
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
        assert "already reached maximum" in caplog.messages[0]
        assert "TIP:" in caplog.messages[0]


async def test_reset_progress(caplog: pytest.LogCaptureFixture, faker: Faker):
    async with ProgressBarData(num_steps=50, description=faker.pystr()) as root:
        assert root._current_steps == pytest.approx(0)  # noqa: SLF001
        assert root.num_steps == 50
        assert root.step_weights is None
        await root.set_(50)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "already reached maximum" not in caplog.text
        await root.set_(51)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "already reached maximum" in caplog.text

        caplog.clear()
        root.reset()

        assert root._current_steps == pytest.approx(-1)  # noqa: SLF001
        assert "already reached maximum" not in caplog.text

        await root.set_(12)
        assert root._current_steps == pytest.approx(12)  # noqa: SLF001
        assert "already reached maximum" not in caplog.text

        await root.set_(51)
        assert root._current_steps == pytest.approx(50)  # noqa: SLF001
        assert "already reached maximum" in caplog.text


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
        async with root.sub_progress(steps=50, description=faker.pystr()) as sub:
            for _ in range(50):
                await sub.update()

        with pytest.raises(RuntimeError):
            async with root.sub_progress(steps=50, description=faker.pystr()) as sub:
                ...


async def test_too_many_updates_does_not_raise_but_show_warning_with_stack(
    caplog: pytest.LogCaptureFixture, faker: Faker
):
    async with ProgressBarData(num_steps=2, description=faker.pystr()) as root:
        assert root.num_steps == 2
        assert root.step_weights is None
        await root.update()
        await root.update()
        await root.update()
        assert "already reached maximum" in caplog.messages[0]
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
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(
            1 / 5
        )
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001
        await root.update()
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(
            1 / 5 + 3 / 5
        )
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


async def test_weighted_progress_bar_with_weighted_sub_progress(
    mocked_progress_bar_cb: mock.Mock, faker: Faker
):
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
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(
            1 / 5
        )
        mocked_progress_bar_cb.reset_mock()
        assert root._current_steps == pytest.approx(1)  # noqa: SLF001

        # 2nd step is a sub progress bar of 5 steps
        async with root.sub_progress(
            steps=5, step_weights=[2, 5, 1, 2, 3], description=faker.pystr()
        ) as sub:
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
        assert mocked_progress_bar_cb.call_args_list[4].args[
            0
        ].percent_value == pytest.approx(1 / 5 + 3 / 5)
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
        async with ProgressBarData(
            num_steps=3, step_weights=[3, 1], description=faker.pystr()
        ):
            ...


async def test_weighted_progress_bar_with_0_weights_is_equivalent_to_standard_progress_bar(
    faker: Faker,
):
    async with ProgressBarData(
        num_steps=3, step_weights=[0, 0, 0], description=faker.pystr()
    ) as root:
        assert root.step_weights == [1, 1, 1, 0]


@pytest.mark.xfail(reason="show how to not use the progress bar")
async def test_concurrent_sub_progress_update_correct_sub_progress(
    mocked_progress_bar_cb: mock.Mock, faker: Faker
):
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
        assert mocked_progress_bar_cb.call_args.args[0].percent_value == pytest.approx(
            2 / 6
        )
