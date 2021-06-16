from pprint import pformat

import pytest
from models_library.projects_state import ProjectLocked, ProjectStatus


@pytest.mark.parametrize(
    "model_cls",
    (ProjectLocked,),
)
def test_projects_state_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_project_locked_with_missing_owner_raises():
    with pytest.raises(ValueError):
        ProjectLocked(**{"value": True, "status": ProjectStatus.OPENED})
