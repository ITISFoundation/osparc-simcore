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
