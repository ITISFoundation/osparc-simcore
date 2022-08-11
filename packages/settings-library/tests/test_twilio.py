from settings_library.twilio import TwilioSettings


def test_twilio_settings_within_envdevel(mock_env_devel_environment: dict[str, str]):
    settings = TwilioSettings.create_from_envs()

    assert (
        settings.TWILIO_MESSAGING_SID
        == mock_env_devel_environment["TWILIO_MESSAGING_SID"]
    )
