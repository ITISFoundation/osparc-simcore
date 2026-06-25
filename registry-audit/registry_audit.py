#!/usr/bin/env python3
import json
import os
import re
import sys

import requests


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: {name} is required", file=sys.stderr)
        sys.exit(1)
    return val


class RegistryClient:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (user, password)
        self._setup_auth()

    def _setup_auth(self):
        """Try Basic auth; fall back to Bearer token if needed."""
        r = self.session.get(f"{self.url}/v2/")
        if r.status_code == 200:
            return
        # Try Bearer
        www = r.headers.get("Www-Authenticate", "")
        m = re.search(r'realm="([^"]+)"', www)
        s = re.search(r'service="([^"]+)"', www)
        if m and s:
            token_r = self.session.get(
                m.group(1),
                params={"service": s.group(1), "scope": "registry:catalog:*"},
            )
            if token_r.ok:
                token = token_r.json().get("token")
                if token:
                    self.session.auth = None
                    self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.url}{path}", **kwargs)

    def catalog(self) -> list[str]:
        repos: list[str] = []
        url = f"{self.url}/v2/_catalog"
        while url:
            r = self.session.get(url)
            r.raise_for_status()
            repos.extend(r.json().get("repositories", []))
            # Follow pagination via Link header
            link = r.headers.get("Link", "")
            m = re.search(r"<([^>]+)>", link)
            if m:
                next_path = m.group(1)
                url = next_path if next_path.startswith("http") else f"{self.url}{next_path}"
                print("  ... fetching next page", file=sys.stderr)
            else:
                url = None
        return repos

    def tags(self, repo: str) -> list[str] | None:
        r = self.get(f"/v2/{repo}/tags/list")
        if not r.ok:
            return None
        return r.json().get("tags") or []

    def manifest(self, repo: str, tag: str) -> dict | None:
        r = self.get(
            f"/v2/{repo}/manifests/{tag}",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
        )
        if not r.ok:
            return None
        data = r.json()
        if "errors" in data:
            return None
        return data

    def blob_json(self, repo: str, digest: str) -> dict | None:
        r = self.get(f"/v2/{repo}/blobs/{digest}")
        if not r.ok:
            return None
        return r.json()


def extract_simcore_version(config: dict) -> str | None:
    """Extract the simcore version from image config labels."""
    labels = config.get("config", {}).get("Labels") or {}
    # Try io.simcore.version (may be JSON-encoded)
    raw = labels.get("io.simcore.version")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed.get("version")
        except (json.JSONDecodeError, TypeError):
            pass
        return raw
    # Fallback
    return labels.get("simcore.service.version")


def main():
    url = get_env("REGISTRY_URL")
    user = get_env("REGISTRY_USER")
    password = get_env("REGISTRY_PASSWORD")

    print("=== Registry Audit ===")
    print(f"Registry: {url}")
    print(f"User:     {user}")
    print()

    print("Testing connection...")
    client = RegistryClient(url, user, password)
    r = client.get("/v2/")
    if r.status_code != 200:
        print(f"ERROR: Cannot reach registry (HTTP {r.status_code})")
        sys.exit(1)
    print("Connection OK\n")

    print("Fetching repository list...")
    repos = client.catalog()
    print(f"Found {len(repos)} repositories\n")

    issues: list[str] = []
    checked = 0

    for i, repo in enumerate(repos, 1):
        checked += 1
        tag_list = client.tags(repo)
        if tag_list is None:
            issues.append(f"NO_TAGS     {repo}  (cannot list tags)")
            continue
        if not tag_list:
            issues.append(f"NO_TAGS     {repo}  (empty tag list)")
            continue

        for tag in tag_list:
            mf = client.manifest(repo, tag)
            if mf is None:
                issues.append(f"BROKEN_TAG  {repo}:{tag}  (manifest not found)")
                continue

            media = mf.get("mediaType", "")
            if "list" in media or "index" in media:
                continue

            cfg = mf.get("config", {})
            digest = cfg.get("digest")
            if not digest:
                issues.append(f"NO_CONFIG   {repo}:{tag}  (no config digest)")
                continue

            blob = client.blob_json(repo, digest)
            if blob is None:
                issues.append(f"NO_BLOB     {repo}:{tag}  (config blob missing)")
                continue

            version = extract_simcore_version(blob)
            if version is None:
                continue  # not a simcore image

            if tag == "latest":
                issues.append(f"LATEST_TAG  {repo}:{tag}  (label={version})")
            elif version != tag:
                issues.append(f"MISMATCH    {repo}:{tag}  (label={version})")

        if i % 10 == 0:
            print(f"  ... checked {i}/{len(repos)} repos", end="\r", file=sys.stderr)

    print(f"\r{' ' * 60}\r", end="", file=sys.stderr)

    for issue in issues:
        print(issue)

    print("\n=== Audit complete ===")
    print(f"Repositories checked: {checked}")
    print(f"Issues found: {len(issues)}")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
