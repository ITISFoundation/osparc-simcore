# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import FastAPI
from simcore_service_payments.api.rest._dependencies import _oauth2_scheme


def test_oauth_scheme(
    mock_patch_setup_rabbitmq_and_rpc: None,
    mock_patch_setup_postgres: None,
    app: FastAPI,
):
    expected_token_url = app.router.url_path_for("login_to_create_access_token")
    assert _oauth2_scheme.model.flows.password.tokenUrl == expected_token_url
