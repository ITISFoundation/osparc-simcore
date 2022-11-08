"""

 $ cd examples
 $ make install-ci
 $ make .env

"""
import os
import tempfile
from pathlib import Path

import osparc
from dotenv import load_dotenv
from osparc.models import File

load_dotenv()
cfg = osparc.Configuration(
    host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
    username=os.environ["OSPARC_API_KEY"],
    password=os.environ["OSPARC_API_SECRET"],
)
print("Entrypoint", cfg.host)


GB = 1024 * 1024 * 1024  # 1GB in bytes


def generate_big_sparse_file(filename, size):
    with open(filename, "wb") as f:
        f.seek(size - 1)
        f.write(b"\1")


# NOTE:
#
# This script reproduces OverflowError in the client due to ssl comms
# SEE https://github.com/ITISFoundation/osparc-issues/issues/617#issuecomment-1204916094

with osparc.ApiClient(cfg) as api_client:

    with tempfile.TemporaryDirectory(
        suffix="_public_api__examples__file_uploads"
    ) as tmpdir:
        local_path = Path(tmpdir) / "large_file.dat"
        generate_big_sparse_file(local_path, size=5 * GB)

        assert local_path.exists()
        assert local_path.stat().st_size == 5 * GB

        files_api = osparc.FilesApi(api_client)

        uploaded_file: File = files_api.upload_file(f"{local_path}")
        print(f"{uploaded_file=}")

        file_in_server = files_api.get_file(uploaded_file.id)
        print(f"{file_in_server=}")
        assert file_in_server == uploaded_file
