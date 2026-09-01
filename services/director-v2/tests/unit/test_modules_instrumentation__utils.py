import time

from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.instrumentation._utils import (
    get_metrics_labels,
    get_running_services_labels,
    track_duration,
)


def test_track_duration():
    with track_duration() as duration:
        time.sleep(0.1)

    assert duration.to_float() > 0.1


def test_get_metrics_labels_uses_empty_string_for_missing_wallet(
    scheduler_data: SchedulerData,
) -> None:
    scheduler_data.wallet_info = None

    assert get_metrics_labels(scheduler_data)["wallet_id"] == ""


def test_get_metrics_labels_with_wallet(scheduler_data: SchedulerData) -> None:
    assert scheduler_data.wallet_info

    labels = get_metrics_labels(scheduler_data)

    assert labels["wallet_id"] == f"{scheduler_data.wallet_info.wallet_id}"
    assert labels["user_id"] == f"{scheduler_data.user_id}"
    assert labels["service_key"] == scheduler_data.key
    assert labels["service_version"] == scheduler_data.version
    assert labels["product_name"] == scheduler_data.product_name
    assert labels["simcore_user_agent"] == scheduler_data.request_simcore_user_agent


def test_get_running_services_labels_uses_none_string_for_missing_wallet(
    scheduler_data: SchedulerData,
) -> None:
    scheduler_data.wallet_info = None

    assert get_running_services_labels(scheduler_data)["wallet_id"] == "None"


def test_get_running_services_labels_with_wallet(scheduler_data: SchedulerData) -> None:
    assert scheduler_data.wallet_info

    labels = get_running_services_labels(scheduler_data)

    assert labels["wallet_id"] == f"{scheduler_data.wallet_info.wallet_id}"
    assert labels["simcore_user_agent"] == scheduler_data.request_simcore_user_agent
    assert labels["product_name"] == scheduler_data.product_name
