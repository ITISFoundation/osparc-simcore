# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from models_library.generated_models.docker_rest_api import (
    DiscreteResourceSpec,
    GenericResource,
    Limit,
    NamedResourceSpec,
    ResourceObject,
    Resources1,
    ServiceSpec,
    TaskSpec,
)
from models_library.services_resources import ResourcesDict, ResourceValue
from simcore_service_catalog.utils.service_resources import (
    merge_service_resources_with_user_specs,
    parse_generic_resource,
)


@pytest.mark.parametrize(
    "generic_resources, expected_resources_dict",
    [
        pytest.param([], ResourcesDict(), id="empty resources"),
        pytest.param(
            ["malformed_generic-resource"], ResourcesDict(), id="malformed resources"
        ),
        pytest.param(
            [{"MalformedResource": {"Kind": "VRAM", "Value": 10}}],
            ResourcesDict(),
            id="badly named resource",
        ),
        pytest.param(
            [{"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 10}}],
            ResourcesDict({"VRAM": ResourceValue(limit=10, reservation=10)}),
            id="well defined discrete resource",
        ),
        pytest.param(
            [{"NamedResourceSpec": {"Kind": "VRAM", "Value": "10"}}],
            ResourcesDict({"VRAM": ResourceValue(limit="10", reservation="10")}),
            id="well defined named resource",
        ),
    ],
)
def test_parse_generic_resources(
    generic_resources: list[Any], expected_resources_dict: ResourcesDict
):
    assert parse_generic_resource(generic_resources) == expected_resources_dict


@pytest.mark.parametrize(
    "service_resources, user_specs, expected_resources",
    [
        pytest.param(
            ResourcesDict(),
            ServiceSpec(),  # type: ignore
            ResourcesDict(),
            id="empty service spec",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec()),  # type: ignore
            ResourcesDict(),
            id="empty task spec",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1())),  # type: ignore
            ResourcesDict(),
            id="empty task resource spec",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit()))),  # type: ignore
            ResourcesDict(),
            id="empty task limit spec",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject()))),  # type: ignore
            ResourcesDict(),
            id="empty task resource spec",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit(NanoCPUs=350)))),  # type: ignore
            ResourcesDict(
                {"CPU": ResourceValue(limit=350 / 10**9, reservation=350 / 10**9)}
            ),
            id="task with cpu limit defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit(NanoCPUs=350, MemoryBytes=123)))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(
                        limit=350 / 10**9, reservation=350 / 10**9
                    ),
                    "RAM": ResourceValue(limit=123, reservation=123),
                }
            ),
            id="task with cpu/ram limit defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit(NanoCPUs=350, MemoryBytes=123, Pids=43)))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(
                        limit=350 / 10**9, reservation=350 / 10**9
                    ),
                    "RAM": ResourceValue(limit=123, reservation=123),
                }
            ),
            id="task with cpu/ram/pids limit defined do not care about pids",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(NanoCPUs=350)))),  # type: ignore
            ResourcesDict(
                {"CPU": ResourceValue(limit=350 / 10**9, reservation=350 / 10**9)}
            ),
            id="task with cpu reservation defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(NanoCPUs=350, MemoryBytes=123)))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(
                        limit=350 / 10**9, reservation=350 / 10**9
                    ),
                    "RAM": ResourceValue(limit=123, reservation=123),
                }
            ),
            id="task with cpu/ram reservation defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit(NanoCPUs=150, MemoryBytes=23), Reservations=ResourceObject(NanoCPUs=350, MemoryBytes=123)))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(
                        limit=150 / 10**9, reservation=150 / 10**9
                    ),
                    "RAM": ResourceValue(limit=23, reservation=23),
                }
            ),
            id="task with cpu/ram limit/reservation bigger defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Limits=Limit(NanoCPUs=650, MemoryBytes=623), Reservations=ResourceObject(NanoCPUs=350, MemoryBytes=123)))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(
                        limit=650 / 10**9, reservation=350 / 10**9
                    ),
                    "RAM": ResourceValue(limit=623, reservation=123),
                }
            ),
            id="task with cpu/ram limit bigger/reservation defined",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(GenericResources=[])))),  # type: ignore
            ResourcesDict(),
            id="task with empty generic reservations",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(GenericResources=[GenericResource()])))),  # type: ignore
            ResourcesDict(),
            id="task with empty generic reservations",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(GenericResources=[GenericResource(DiscreteResourceSpec=DiscreteResourceSpec()), GenericResource(NamedResourceSpec=NamedResourceSpec())])))),  # type: ignore
            ResourcesDict(),
            id="task with empty generic reservations",
        ),
        pytest.param(
            ResourcesDict(),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(GenericResources=[GenericResource(DiscreteResourceSpec=DiscreteResourceSpec(Kind="Fake", Value=432)), GenericResource(NamedResourceSpec=NamedResourceSpec(Kind="NamedFake", Value="myfake"))])))),  # type: ignore
            ResourcesDict(
                {
                    "Fake": ResourceValue(limit=432, reservation=432),
                    "NamedFake": ResourceValue(limit="myfake", reservation="myfake"),
                }
            ),
            id="task with generic reservations",
        ),
        pytest.param(
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                    "Fake": ResourceValue(limit=27, reservation=12),
                    "NamedFake": ResourceValue(limit=27, reservation=12),
                }
            ),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1(Reservations=ResourceObject(GenericResources=[GenericResource(DiscreteResourceSpec=DiscreteResourceSpec(Kind="Fake", Value=432)), GenericResource(NamedResourceSpec=NamedResourceSpec(Kind="NamedFake", Value="myfake"))])))),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                    "Fake": ResourceValue(limit=432, reservation=432),
                    "NamedFake": ResourceValue(limit="myfake", reservation="myfake"),
                }
            ),
            id="merge task resources overrides generic reservations",
        ),
        pytest.param(
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            ServiceSpec(TaskTemplate=TaskSpec(Resources=Resources1())),  # type: ignore
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            id="merge task empty user resources does not override",
        ),
        pytest.param(
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            ServiceSpec(  # type: ignore
                TaskTemplate=TaskSpec(  # type: ignore
                    Resources=Resources1(Limits=Limit(NanoCPUs=3 * 10**9))  # type: ignore
                )
            ),
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=3, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            id="merge task change cpu limit does not change reservation",
        ),
        pytest.param(
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=10, reservation=2),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            ServiceSpec(  # type: ignore
                TaskTemplate=TaskSpec(  # type: ignore
                    Resources=Resources1(  # type: ignore
                        Limits=Limit(NanoCPUs=1 * 10**9),  # type: ignore
                    )
                )
            ),
            ResourcesDict(
                {
                    "CPU": ResourceValue(limit=1, reservation=1),
                    "RAM": ResourceValue(limit=27, reservation=12),
                }
            ),
            id="merge task change cpu limit does change reservation as well",
        ),
    ],
)
def test_merge_service_resources_with_user_specs(
    service_resources: ResourcesDict,
    user_specs: ServiceSpec,
    expected_resources: ResourcesDict,
):
    merged_resources = merge_service_resources_with_user_specs(
        service_resources, user_specs
    )
    assert all(key in expected_resources for key in merged_resources)
    assert all(key in merged_resources for key in expected_resources)
    for resource_key, resource_value in merged_resources.items():
        # NOTE: so that float values are compared correctly
        assert resource_value.model_dump() == pytest.approx(
            expected_resources[resource_key].model_dump()
        )
