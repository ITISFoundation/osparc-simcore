# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from asyncio import Future
from pathlib import Path
from shutil import make_archive

import pytest
from simcore_sdk.node_data import data_manager


@pytest.fixture
def create_files():
    created_files = []
    def _create_files(number: int, folder: Path):
        
        for i in range(number):
            file_path = folder / "{}.test".format(i)
            file_path.write_text("I am test file number {}".format(i))
            assert file_path.exists()
        
        #cleanup
        for file_path in created_files:
            file_path.unlink()
        
    return _create_files
    

async def test_push(loop, mocker, tmpdir, create_files):
    # create some files
    assert tmpdir.exists()
    # create a folder to compress from
    test_folder = Path(tmpdir) / "test_folder"
    test_folder.mkdir()
    assert test_folder
    # create a folder to compress in
    test_compression_folder = Path(tmpdir) / "test_compression_folder"
    test_compression_folder.mkdir()
    assert test_compression_folder

    mock_filemanager = mocker.patch('simcore_sdk.node_data.data_manager.filemanager', spec=True)
    mock_filemanager.upload_file.return_value = Future()
    mock_filemanager.upload_file.return_value.set_result("")
    mock_config = mocker.patch('simcore_sdk.node_data.data_manager.config', spec=True)    
    mock_config.PROJECT_ID = "some funky ID"
    mock_config.NODE_UUID = "another funky ID"
    mock_temporary_directory = mocker.patch('simcore_sdk.node_data.data_manager.TemporaryDirectory')
    mock_temporary_directory.return_value.__enter__.return_value = test_compression_folder
    create_files(10, test_folder)
    
    assert len(list(test_folder.glob("**/*"))) == 10
    for file_path in test_folder.glob("**/*.*"):
        assert file_path.exists()
        # test push file by file
        await data_manager.push(file_path)
        mock_temporary_directory.assert_not_called()
        mock_filemanager.upload_file.assert_called_once_with(local_file_path=file_path, 
                                                        s3_object="{}/{}/{}".format(mock_config.PROJECT_ID, mock_config.NODE_UUID, file_path.name), 
                                                        store_id=0)
        mock_filemanager.reset_mock()
    
    await data_manager.push(test_folder)

    mock_temporary_directory.assert_called_once()
    mock_filemanager.upload_file.assert_called_once_with(local_file_path=(test_compression_folder / "{}.zip".format(test_folder.stem)), 
                                                        s3_object="{}/{}/{}.zip".format(mock_config.PROJECT_ID, mock_config.NODE_UUID, test_folder.stem), 
                                                        store_id=0)
    
    assert (test_compression_folder / "{}.zip".format(test_folder.stem)).exists()




async def test_pull(loop, mocker, tmpdir, create_files):
    assert tmpdir.exists()
    # create a folder to compress from
    test_fake_folder = Path(tmpdir) / "test_fake_folder"
    test_fake_folder.mkdir()
    assert test_fake_folder
    # create the test folder
    test_folder = Path(tmpdir) / "test_folder"
    test_folder.mkdir()
    assert test_folder
    # create a folder to compress in
    test_compression_folder = Path(tmpdir) / "test_compression_folder"
    test_compression_folder.mkdir()
    assert test_compression_folder
    # create the zip file
    create_files(12, test_fake_folder)
    compressed_file_name = test_compression_folder / test_folder.stem
    archive_file = make_archive(compressed_file_name, "zip", root_dir=test_fake_folder)
    assert Path(archive_file).exists()

    mock_filemanager = mocker.patch('simcore_sdk.node_data.data_manager.filemanager', spec=True)
    mock_filemanager.download_file.return_value = Future()
    mock_filemanager.download_file.return_value.set_result("")
    mock_config = mocker.patch('simcore_sdk.node_data.data_manager.config', spec=True)    
    mock_config.PROJECT_ID = "some funky ID"
    mock_config.NODE_UUID = "another funky ID"
    mock_temporary_directory = mocker.patch('simcore_sdk.node_data.data_manager.TemporaryDirectory')
    mock_temporary_directory.return_value.__enter__.return_value = test_compression_folder

    await data_manager.pull(test_folder)
    mock_temporary_directory.assert_called_once()
    mock_filemanager.download_file.assert_called_once_with(local_file_path=(test_compression_folder / "{}.zip".format(test_folder.stem)), 
                                                        s3_object="{}/{}/{}.zip".format(mock_config.PROJECT_ID, mock_config.NODE_UUID, test_folder.stem), 
                                                        store_id=0)
    assert len(list(test_folder.glob("**/*"))) == 12
