from textwrap import dedent


def compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )
