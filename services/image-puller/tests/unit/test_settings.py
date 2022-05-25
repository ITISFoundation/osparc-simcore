from simcore_service_image_puller.settings import ImagePullerSettings


def test_image_puller_settings(settings: ImagePullerSettings) -> None:
    print(settings.json(indent=2))
    assert settings
