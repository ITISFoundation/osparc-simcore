# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from models_library.projects_pipeline import ComputationTask


def test_computation_task_model():
    example = ComputationTask.Config.schema_extra["example"]
    print(example)

    model_instance = ComputationTask.parse_obj(example)
    assert model_instance
