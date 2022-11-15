""" Helper to request data from docker-registry


NOTE: this could be used as draft for https://github.com/ITISFoundation/osparc-simcore/issues/2165
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx


@dataclass
class RegistryConfig:
    url: str
    auth: tuple[str, str]


RepoName = str
RepoTag = str


class Registry:
    # SEE https://docs.docker.com/registry/spec/api
    # SEE  https://github.com/moby/moby/issues/9015

    def __init__(self, **data):
        data.setdefault("url", f'https://{os.environ.get("REGISTRY_URL")}')
        data.setdefault(
            "auth", (os.environ.get("REGISTRY_USER"), os.environ.get("REGISTRY_PW"))
        )
        self.data = RegistryConfig(**data)

    def __str__(self) -> str:
        return f"<Docker Registry f{self.data.url}>"

    def api_version_check(self):
        # https://docs.docker.com/registry/spec/api/#api-version-check

        r = httpx.get(f"{self.data.url}/v2/", auth=self.data.auth)
        r.raise_for_status()

    def iter_repositories(self, limit: int = 100) -> Iterator[RepoName]:
        def _req(**kwargs):
            r = httpx.get(auth=self.data.auth, **kwargs)
            r.raise_for_status()

            yield from r.json()["repositories"]

            if link := r.headers.get("Link"):
                #  until the Link header is no longer set in the response
                # SEE https://docs.docker.com/registry/spec/api/#pagination-1
                # ex=.g. '</v2/_catalog?last=simcore%2Fservices%2Fcomp%2Fcontrolcore-mmpc&n=5>; rel="next"'
                if m := re.match(r'<([^><]+)>;\s+rel=([\w"]+)', link):
                    next_page = m.group(1)
                    yield from _req(url=next_page)

        assert limit > 0
        query = {"n": limit}

        yield from _req(url=f"{self.data.url}/v2/_catalog", params=query)

    def get_digest(self, repo_name: str, repo_reference: str) -> str:
        r = httpx.head(
            f"{self.data.url}/v2/{repo_name}/manifests/{repo_reference}",
            auth=self.data.auth,
        )
        r.raise_for_status()
        assert r.status_code == 200
        digest = r.headers["Docker-Content-Digest"]
        return digest

    def check_manifest(self, repo_name: RepoName, repo_reference: str) -> bool:
        r = httpx.head(
            f"{self.data.url}/v2/{repo_name}/manifests/{repo_reference}",
            auth=self.data.auth,
        )
        if r.status_code == 400:
            return False
        # some other error?
        r.raise_for_status()
        return True

    def list_tags(self, repo_name: RepoName) -> list[RepoTag]:
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

        # manifest formats and their content types: https://docs.docker.com/registry/spec/manifest-v2-1/,
        # see format https://github.com/moby/moby/issues/8093
        manifest = r.json()
        return manifest


def get_metadata(image_v1: str) -> dict[str, Any]:
    """Extracts metadata object from 'io.simcore.*' labels

    image_v1: v1 compatible string encoded json for each layer
    """
    labels = json.loads(image_v1).get("config", {}).get("Labels", [])
    meta = {}
    for key in labels:
        if key.startswith("io.simcore."):
            meta.update(**json.loads(labels[key]))
    return meta


SKIP, SUCCESS, FAILED = "[skip]", "[ok]", "[failed]"


def download_all_registry_metadata(dest_dir: Path):
    registry = Registry()

    print("Starting", registry)

    count = 0
    for repo in registry.iter_repositories(limit=500):

        # list tags
        try:
            tags = registry.list_tags(repo_name=repo)
        except httpx.HTTPStatusError as err:
            print(f"Failed to get tags from {repo=}", err, FAILED)
            continue

        # get manifest
        folder = dest_dir / Path(repo)
        folder.mkdir(parents=True, exist_ok=True)
        for tag in tags:
            path = folder / f"metadata-{tag}.json"
            if not path.exists():
                try:
                    manifest = registry.get_manifest(repo_name=repo, repo_reference=tag)

                    meta = get_metadata(
                        image_v1=manifest["history"][0]["v1Compatibility"]
                    )
                    with path.open("wt") as fh:
                        json.dump(meta, fh, indent=1)
                    print("downloaded", path, SUCCESS)
                    count += 1
                except Exception as err:  # pylint: disable=broad-except
                    print("Failed", path, err, FAILED)
                    path.unlink(missing_ok=True)
            else:
                print("found", path, SKIP)
                count += 1
    print("\nDownloaded", count, "metadata files from", registry.data.url)


if __name__ == "__main__":
    import sys

    dest = Path(sys.argv[1])
    download_all_registry_metadata(dest_dir=dest)
