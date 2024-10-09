import asyncio

from pydantic import ByteSize


async def get_size_bash_async(path) -> ByteSize:
    try:
        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            "du",
            "-sb",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for the subprocess to complete
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # Parse the output
            size = ByteSize(stdout.decode().split()[0])
            return size
        else:
            print(f"Error: {stderr.decode()}")
            raise ValueError
    except Exception as e:
        raise e


async def remove_write_permissions_bash_async(path) -> None:
    try:
        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            "chmod",
            "-R",
            "a-w",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for the subprocess to complete
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return
        else:
            print(f"Error: {stderr.decode()}")
            raise ValueError
    except Exception as e:
        raise e
