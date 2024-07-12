from textwrap import dedent


def compose_user_data(bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{bash_command}
"""
    )
