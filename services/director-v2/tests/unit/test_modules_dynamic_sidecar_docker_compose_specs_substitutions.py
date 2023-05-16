from simcore_service_director_v2.modules.dynamic_sidecar.docker_compose_specs_substitutions import (
    substitute_request_environments,
    substitute_session_environments,
    substitute_vendor_environments,
)


def test_it():
    assert substitute_session_environments
    assert substitute_vendor_environments
    assert substitute_request_environments

    await substitute_session_environments(app, pod_compose_spec, user_id, product_name)
