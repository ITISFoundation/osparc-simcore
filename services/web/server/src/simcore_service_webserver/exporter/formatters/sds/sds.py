from pathlib import Path

from simcore_service_webserver.exporter.formatters.sds.text_files import (
    write_text_files,
)
from simcore_service_webserver.exporter.formatters.sds.xlsx import write_xlsx_files


def write_sds_directory_content(base_path: Path) -> None:
    # TODO: migrate formatter_v1 call it here to produce the output in the base_path
    write_text_files(base_path=base_path)
    write_xlsx_files(base_path=base_path)


if __name__ == "__main__":
    # TODO: with some data, some being fake inject it into the
    # templates to generate all that we need
    import os

    path_to_store = Path("/tmp/sds_dir")  # nosec

    # recreate dir
    os.system(f"rm -rf {str(path_to_store)}")  # nosec
    path_to_store.mkdir(parents=True, exist_ok=True)

    write_sds_directory_content(base_path=path_to_store)
