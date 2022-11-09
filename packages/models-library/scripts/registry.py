import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx

# TODO: use this for registry!
#  https://github.com/moby/moby/issues/9015


@dataclass
class RegistryData:
    url: str
    auth: tuple[str, str]


RepoName = str
RepoTag = str


class Registry:
    def __init__(self, **data):
        self.data = RegistryData(**data)

    def api_version_check(self):
        # https://docs.docker.com/registry/spec/api/#api-version-check

        r = httpx.get(f"{self.data.url}/v2/", auth=self.data.auth)
        # print(r.text)
        r.raise_for_status()

    def iter_repositories(self, limit: int = 100) -> Iterator[RepoName]:
        assert limit > 0
        query = {"n": limit}

        r = httpx.get(f"{self.data.url}/v2/_catalog", auth=self.data.auth, params=query)
        r.raise_for_status()
        yield from r.json()["repositories"]

        print(r.headers["Link"])

        # r.headers["Link"]

    def get_digest(self, repo_name: str, repo_reference: str) -> str:
        r = httpx.head(
            f"{self.data.url}/v2/{repo_name}/manifests/{repo_reference}",
            auth=self.data.auth,
        )
        if r.status_code == 200:
            digest = r.headers["Docker-Content-Digest"]
            return digest
        r.raise_for_status()

    def check_manifest(self, repo_name: RepoName, repo_reference: str) -> bool:
        r = httpx.head(
            f"{self.data.url}/v2/{repo_name}/manifests/{repo_reference}",
            auth=self.data.auth,
        )
        if r.status_code == 400:
            return False

        r.raise_for_status()
        return True

    def get_tags(self, repo_name: RepoName) -> list[RepoTag]:
        r = httpx.get(
            f"{self.data.url}/v2/{repo_name}/tags/list",
            auth=self.data.auth,
        )
        r.raise_for_status()
        data = r.json()
        assert data["name"] == repo_name
        return data["tags"]

    def get_manifest(self, repo_name: str, repo_reference: str):
        r = httpx.get(
            f"{self.data.url}/v2/{repo_name}/manifests/{repo_reference}",
            auth=self.data.auth,
        )
        r.raise_for_status()
        # print(r.text)

        #
        # manifest formats and their content types: https://docs.docker.com/registry/spec/manifest-v2-1/,
        #
        # see format https://github.com/moby/moby/issues/8093
        manifest = r.json()
        return manifest


def get_meta(image_v1: str):
    # image_v1: accepts v1 compatible string encoded json for each layer
    labels = json.loads(image_v1).get("config", {}).get("Labels", [])
    meta = {}
    for key in labels:
        # TODO: simcore.service.settings
        if key.startswith("io.simcore."):
            meta.update(**json.loads(labels[key]))
    return meta


def demo1():
    for n, h in enumerate(manifest["history"]):
        # pprint(json.loads(image_v1))
        meta = get_meta(image_v1=h["v1Compatibility"])
        print(n, json.dumps(meta, indent=1))


def demo2():
    registry = Registry(
        url="https://registry.osparc-master.speag.com", auth=("admin", "adminadmin")
    )

    # All versions of an image are stored in a repository
    repo_name = (
        "simcore/services/comp/ascent-runner"  # = image name prefix (w/o tag after ':')
    )
    repo_reference = "1.0.0"  #  = The reference may include a tag or digest!

    manifest = registry.get_manifest(repo_name=repo_name, repo_reference=repo_reference)

    meta = get_meta(image_v1=manifest["history"][0]["v1Compatibility"])
    with open("metadata.json", "wt") as fh:
        json.dump(meta, fh, indent=1)


if __name__ == "__main__":
    registry = Registry(
        url="https://registry.osparc-master.speag.com", auth=("admin", "adminadmin")
    )

    for repo in registry.iter_repositories():
        folder = Path(repo)
        folder.mkdir(parents=True, exist_ok=True)
        for tag in registry.get_tags(repo_name=repo):
            path = folder / f"metadata-{tag}.json"
            if not path.exists():
                try:
                    manifest = registry.get_manifest(repo_name=repo, repo_reference=tag)

                    meta = get_meta(image_v1=manifest["history"][0]["v1Compatibility"])
                    with path.open("wt") as fh:
                        json.dump(meta, fh, indent=1)
                except Exception as err:
                    print(f"Failed {path}", err)
                    path.unlink(missing_ok=True)
