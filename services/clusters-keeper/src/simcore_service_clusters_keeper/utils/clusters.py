def create_startup_script() -> str:
    return "\n".join(
        [
            "git clone https://github.com/ITISFoundation/osparc-simcore.git",
            "cd osparc-simcore/services/osparc-gateway-server",
            "make up-latest",
        ]
    )
