# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


# ONLY FOR DEVELOPMENT

import asyncio

import aiodocker
from aiodocker.volumes import DockerVolume
from models_library.generated_models.docker_rest_api import Volume
from pydantic import parse_obj_as, validator
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


async def test_it():
    class VolumeGet(Volume):
        @validator("Labels", "Options", pre=True)
        @classmethod
        def none_to_dict(cls, v):
            if v is None:
                return {}
            return v

    docker = aiodocker.Docker()

    data: dict = await docker.volumes.list()
    # ['Volumes', 'Warnings']

    volumes = parse_obj_as(list[VolumeGet], data["Volumes"])

    LABELS = {"run_id", "source"}

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def _delete(name):
        dv = DockerVolume(docker, name)
        print("Deleting", await dv.show())  # show is like inspect!?
        await dv.delete()

    to_delete = []
    for volume in volumes:
        if LABELS.issubset(set(volume.Labels.keys())):
            to_delete.append(_delete(volume.Name))

    results = await asyncio.gather(*to_delete, return_exceptions=True)
    assert not any(isinstance(r, Exception) for r in results)

    await docker.close()
