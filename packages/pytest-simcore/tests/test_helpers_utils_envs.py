from pathlib import Path
from textwrap import dedent

from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, load_dotenv


def test_load_envfile(tmp_path: Path):

    envfile = tmp_path / ".env"
    envfile.write_text(
        dedent(
            """
            NAME=foo
            INDEX=33
            ONLY_NAME=
            NULLED=null
        """
        )
    )

    envs: EnvVarsDict = load_dotenv(envfile, verbose=True)

    assert {
        "NAME": "foo",
        "INDEX": "33",
        "NULLED": "null",
        "ONLY_NAME": "",
    } == envs
