# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid
from functools import lru_cache

from models_library.projects_nodes_io import SimcoreS3FileID
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


def create_reverse_dns(*resource_name_parts) -> str:
    """
    Returns a name for the resource following the reverse domain name notation
    """
    # See https://en.wikipedia.org/wiki/Reverse_domain_name_notation
    return "io.simcore.storage" + ".".join(map(str, resource_name_parts))


@lru_cache
def create_resource_uuid(*resource_name_parts) -> uuid.UUID:
    revers_dns = create_reverse_dns(*resource_name_parts)
    return uuid.uuid5(uuid.NAMESPACE_DNS, revers_dns)


async def test_create_soft_link(
    simcore_s3_dsm: SimcoreS3DataManager, user_id: int, output_file: FileMetaData
):
    api_file_id = create_resource_uuid(
        output_file.project_id, output_file.node_id, output_file.file_name
    )
    file_name = output_file.file_name

    link_file: FileMetaData = await simcore_s3_dsm.create_soft_link(
        user_id,
        output_file.file_id,
        SimcoreS3FileID(f"api/{api_file_id}/{file_name}"),
    )
    assert isinstance(link_file, FileMetaData)

    # copy:
    #     - you have two different versions of the file.
    #     - if you edit one, the other one stays the same.
    #     - if you delete one, the other one stays there, but it may not be identical if it was edited
    #     - twice as much disk space used (two different files)
    # hard link:
    #     - you have one file with two different filenames.
    #     - If you edit one, it gets edited in all filename locations
    #     - if you delete one, it still exists in other places
    #     - only one file on disk
    # soft link:
    #     - you have one file with one filename and a pointer to that file with the other filename.
    #     - if you edit the link its really editing the original file
    #     - if you delete the file the link is broken
    #     - if you remove the link the file stays in place.
    #     - only one file on disk
    #
    #
    #
    # 6686134 -rw-rw-r--  1 crespo crespo 1371 Apr 14 14:53 TODO.md
    # 6686594 -rw-rw-r--  2 crespo crespo    6 Mar  9  2020 VERSION
    # 6686594 -rw-rw-r--  2 crespo crespo    6 Mar  9  2020 VERSION-hard
    # 6686197 lrwxrwxrwx  1 crespo crespo    7 Apr 14 14:48 VERSION-link -> VERSION

    assert link_file.file_uuid == f"api/{api_file_id}/{file_name}"
    assert link_file.file_id == link_file.file_uuid
    assert link_file.object_name == output_file.object_name
    assert link_file.entity_tag == output_file.entity_tag
    assert link_file.is_soft_link

    # TODO: in principle we keep this ...
    # assert output_file.created_at < link_file.fmd.created_at
    # assert output_file.last_modified < link_file.fmd.last_modified

    # can find
    files_list = await simcore_s3_dsm.search_owned_files(
        user_id=user_id,
        file_id_prefix=f"api/{api_file_id}/{file_name}",
    )
    assert len(files_list) == 1
    assert files_list[0] == link_file

    # can get
    got_file = await simcore_s3_dsm.get_file(
        user_id, SimcoreS3FileID(f"api/{api_file_id}/{file_name}")
    )

    assert got_file == link_file

    # Moving the offset will skip the first search hit
    files_list_without_first_hit = await simcore_s3_dsm.search_owned_files(
        user_id=user_id,
        file_id_prefix=f"api/{api_file_id}/{file_name}",
        # NOTE: that only one
        offset=1,
    )
    assert len(files_list_without_first_hit) == 0
