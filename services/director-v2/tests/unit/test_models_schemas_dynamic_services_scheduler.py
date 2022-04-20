from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
import json
from copy import deepcopy


def test_regression_as_label_data(scheduler_data: SchedulerData) -> None:
    # old tested implementation
    scheduler_data_copy = deepcopy(scheduler_data)
    scheduler_data_copy.compose_spec = json.dumps(scheduler_data_copy.compose_spec)
    json_encoded = scheduler_data_copy.json()

    # using pydantic's internals
    label_data = scheduler_data.as_label_data()

    parsed_json_encoded = SchedulerData.parse_raw(json_encoded)
    parsed_label_data = SchedulerData.parse_raw(label_data)
    assert parsed_json_encoded == parsed_label_data
