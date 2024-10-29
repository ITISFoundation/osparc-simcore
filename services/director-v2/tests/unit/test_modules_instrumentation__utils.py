import time

from simcore_service_director_v2.modules.instrumentation._utils import track_duration


def test_track_duration():
    with track_duration() as duration:
        time.sleep(0.1)

    assert duration.to_float() > 0.1
