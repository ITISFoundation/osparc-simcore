from uuid import uuid4

import pytest
from simcore_service_director_v2.models.schemas.comp_scheduler import Image, TaskIn


@pytest.mark.parametrize(
    "image, exp_requirements_str",
    [
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=False,
                requires_mpi=False,
            ),
            "cpu",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=True,
                requires_mpi=False,
            ),
            "gpu",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=False,
                requires_mpi=True,
            ),
            "mpi",
        ),
        (
            Image(
                name="simcore/services/comp/itis/sleeper",
                tag="1.0.0",
                requires_gpu=True,
                requires_mpi=True,
            ),
            "gpu:mpi",
        ),
    ],
)
def test_dask_task_in_model(image: Image, exp_requirements_str: str):
    node_id = uuid4()
    dask_task = TaskIn.from_node_image(node_id, image)
    assert dask_task
    assert dask_task.node_id == node_id
    assert dask_task.runtime_requirements == exp_requirements_str
