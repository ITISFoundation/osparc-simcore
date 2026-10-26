---
applyTo: '.github/workflows/**'
---

# GitHub workflow instructions

- Follow the naming convention in
  [`.github/workflows/README.md`](../workflows/README.md).
- A workflow that triggers on `pull_request_target` is allowed by an Actions
  event policy that matches it by file path, so renaming or moving it means
  updating that policy in the same change:
  <https://gh.io/securely-using-pull_request_target>.
- Reference a third-party action by full commit SHA plus a trailing comment with
  the release version it resolves to, e.g.
  `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.
  Do not use a floating tag. Keep the SHA and its comment in sync; Dependabot
  updates both. When adding an action, resolve the tag to its commit with
  `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha`.
