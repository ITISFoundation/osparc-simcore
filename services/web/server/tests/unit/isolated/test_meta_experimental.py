import collections.abc
from typing import Generator, Iterator, get_origin, get_type_hints

import pytest
from models_library.frontend_services_catalog import is_iterator_service
from models_library.services import ServiceDockerData
from simcore_service_webserver.meta_experimental import SumDiffData, SumDiffDef

## HELPERS -------------------------------------------------


def infinite_stream_as_iter(start: int) -> Iterator[int]:
    while True:
        yield start
        start += 1


def infinite_stream_as_gen(start: int) -> Generator[int, None, None]:
    while True:
        yield start
        start += 1


def distance(start: int, end: int) -> int:
    return abs(end - start)


## FIXTURES -------------------------------------------------


## TESTS -------------------------------------------------


@pytest.mark.parametrize(
    "func,is_iter",
    [
        (infinite_stream_as_iter, True),
        (infinite_stream_as_gen, True),
        (distance, False),
    ],
)
def test_check_iterables(func, is_iter):
    types = get_type_hints(func)
    return_cls = get_origin(types["return"])

    # SEE https://docs.python.org/3/library/collections.abc.html#collections-abstract-base-classes
    if is_iter:
        assert return_cls
        assert issubclass(return_cls, collections.abc.Iterable)
    else:
        assert not return_cls or not issubclass(return_cls, collections.abc.Iterable)


def test_it():
    print(SumDiffData.schema_json(indent=2))

    node1 = SumDiffData(inputs={"x": 3, "y": 44})

    node1_w_results = SumDiffData.from_io(
        node1.inputs,
        SumDiffDef.run_with_model(node1.inputs),
    )

    returned = SumDiffDef.run_fun(x=3, y=44)
    node2_w_results = SumDiffData(inputs={"x": 3, "y": 44}, outputs=returned)

    assert node1_w_results == node2_w_results

    assert not SumDiffDef.is_iterable()

    assert SumDiffDef.is_iterable() == is_iterator_service(SumDiffDef.info.key)

    ds_model = SumDiffDef.to_dockerdata()
    assert isinstance(ds_model, ServiceDockerData)
