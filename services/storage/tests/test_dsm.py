import pytest

from simcore_service_dsm.dsm import Dsm
from simcore_service_dsm.models import FileMetaData

import utils
import uuid
import os
import urllib
import filecmp

import pdb

from pprint import pprint

def test_mockup(dsm_mockup_db):
    assert len(dsm_mockup_db)

async def test_dsm_s3(dsm_mockup_db, postgres_service, s3_client):
    id_name_map = {}
    id_file_count = {}
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if not md.user_id in id_name_map:
            id_name_map[md.user_id] = md.user_name
            id_file_count[md.user_id] = 1
        else:
            id_file_count[md.user_id] = id_file_count[md.user_id] + 1

    dsm = Dsm(postgres_service, s3_client)
    
    # list files for every user
    for id in id_file_count:
        data = await dsm.list_files(user_id=id, location="simcore.s3")
        assert len(data) == id_file_count[id]

    # Get files from bob from the project biology
    bob_id = 0
    for id in id_name_map.keys():
        if id_name_map[id] == "bob":
            bob_id = id
            break
    assert not bob_id == 0

    data = await dsm.list_files(user_id=bob_id, location="simcore.s3", regex="biology")
    bobs_files = []
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if md.user_id == bob_id and md.project_name == "biology":
            bobs_files.append(d)

    assert len(data) == len(bobs_files)

    for d in data:
        await dsm.delete_file(user_id=d.user_id, location="simcore.s3", fmd=d)

    # now we should have less items
    new_size = 0
    for id in id_file_count:
        data = await dsm.list_files(user_id=id, location="simcore.s3")
        new_size = new_size + len(data)

    assert len(dsm_mockup_db) == new_size + len(bobs_files)
    

def create_file_on_s3(postgres_url, s3_client, tmp_file):
    utils.create_tables(url=postgres_url)
    bucket_name = utils.bucket_name()
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)


    # create file and upload
    filename = os.path.basename(tmp_file)
    project_id = 22
    node_id = 1006
    file_id = uuid.uuid4()
   
    d = {   'object_name' : os.path.join(str(project_id), str(node_id), str(file_id)),
            'bucket_name' : bucket_name,
            'file_id' : str(file_id),
            'file_name' : filename,
            'user_id' : 42,
            'user_name' : "starbucks",
            'location' : "simcore.s3",
            'project_id' : project_id,
            'project_name' : "battlestar",
            'node_id' : node_id,
            'node_name' : "this is the name of the node"
        }   

    fmd = FileMetaData(**d)
    ## TODO: acutally upload the file gettin a upload link
    return fmd

async def test_links_s3(postgres_service, s3_client, tmp_files):
    tmp_file = tmp_files(1)[0]
    fmd = create_file_on_s3(postgres_service, s3_client, tmp_file)

    dsm = Dsm(postgres_service, s3_client)

    up_url = await dsm.upload_link(fmd)
    with open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    tmp_file2 = tmp_file + ".rec"
    user_id = 0
    down_url = await dsm.download_link(user_id, fmd, "simcore.s3")

    urllib.request.urlretrieve(down_url, tmp_file2)

    assert filecmp.cmp(tmp_file2, tmp_file)


#NOTE: Below tests directly access the datcore platform, use with care!

async def test_dsm_datcore(postgres_service, s3_client):
    utils.create_tables(url=postgres_service)
    dsm = Dsm(postgres_service, s3_client)
    user_id = 0
    data = await dsm.list_files(user_id=user_id, location="datcore")
    assert len(data)

    #pdb.set_trace()
    fmd_to_delete = data[0]
    print("Deleting", fmd_to_delete.bucket_name, fmd_to_delete.object_name)
    await dsm.delete_file(user_id, "datcore", fmd_to_delete)

async def test_dsm_s3_to_datcore(postgres_service, s3_client, tmp_files):
    tmp_file = tmp_files(1)[0]
    fmd = create_file_on_s3(postgres_service, s3_client, tmp_file)

    dsm = Dsm(postgres_service, s3_client)

    up_url = await dsm.upload_link(fmd)
    with open(tmp_file, 'rb') as fp:
        d = fp.read()
        req = urllib.request.Request(up_url, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

    # given the fmd, upload to datcore
    tmp_file2 = tmp_file + ".fordatcore"
    user_id = 0
    down_url = await dsm.download_link(user_id, fmd, "simcore.s3" )
    urllib.request.urlretrieve(down_url, tmp_file2)
    fmd.location = "datcore"
    # now we have the file locally, upload the file
    

async def test_dsm_datcore_to_s3(postgres_service, s3_client, tmp_files):
    utils.create_tables(url=postgres_service)
    dsm = Dsm(postgres_service, s3_client)
    user_id = 0
    data = await dsm.list_files(user_id=user_id, location="datcore")
    assert len(data)

    #pdb.set_trace()
    fmd_to_get = data[0]
    url = await dsm.download_link(user_id, fmd_to_get, "datcore")
    print(url)


    



        

