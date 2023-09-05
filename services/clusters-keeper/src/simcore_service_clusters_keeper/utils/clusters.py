from ..core.settings import ApplicationSettings


def create_startup_script(app_settings: ApplicationSettings) -> str:
    return "\n".join(
        [
            "git clone --depth=1 https://github.com/ITISFoundation/osparc-simcore.git",
            "cd osparc-simcore/services/osparc-gateway-server",
            "make config",
            f"echo 'c.Authenticator.password = \"{app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD.get_secret_value()}\"' >> .osparc-dask-gateway-config.py",
            f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG} make up",
        ]
    )
