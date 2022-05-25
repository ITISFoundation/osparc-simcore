from simcore_service_image_puller.settings import ImagePullerSettings


def test_image_puller_settings() -> None:
    settings = ImagePullerSettings.create_from_envs()
    print(settings.json(indent=2))
    assert settings
