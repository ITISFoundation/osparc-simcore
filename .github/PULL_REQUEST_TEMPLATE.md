<!-- Title Annotations:

  WIP: work in progress
  🐛    Fix a bug.
  ✨    Introduce new features.
  🎨    Enhance existing feature.
  ♻️    Refactor code.
  🚑️    Critical hotfix.
  ⚗️    Perform experiments.
  ⬆️    Upgrade dependencies.
  📝    Add or update documentation.
  🔨    Add or update development scripts.
  🔒️    Fix security issues.
  ⚠️    Changes in ops configuration etc. are required before deploying.
        [ Please add a link to the associated ops-issue or PR, such as in https://github.com/ITISFoundation/osparc-ops-environments or https://git.speag.com/oSparc/osparc-infra ]
  🗃️    Database table changed (relevant for devops).
  👽️    Public API changes (meaning: dev features are moved to being exposed in production)
  🚨    Do manual testing when deployed

or from https://gitmoji.dev/
-->

## What do these changes do?

<!-- Badge to openapi specs
[![ReDoc](https://img.shields.io/badge/OpenAPI-ReDoc-85ea2d?logo=openapiinitiative)](https://redocly.github.io/redoc/?url=HERE-URL-TO-RAW-FILE)
-->


## Related issue/s

<!-- Link pull request to an issue
  SEE https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue

- resolves ITISFoundation/osparc-issues#428
- fixes #26
-->


## How to test

<!-- Give REVIEWERS some hits or code snippets on how could this be tested -->

## Dev-ops checklist

- [ ] No ENV changes or I properly updated ENV ([read the instruction](https://git.speag.com/oSparc/osparc-ops-deployment-configuration/-/blob/configs/README.md?ref_type=heads#how-to-update-env-variables))

<!-- Some checks that might help your code run stable on production, and help devops assess criticality.
Modified from https://oschvr.com/posts/what-id-like-as-sre/

- How can DevOps check the health of the service ?
- How can DevOps safely and gracefully restart the service ?
- How and why would this code fail ?
- What kind of metrics are you exposing ?
- Is there any documentation/design specification for the service ?
- How (e.g. through which loglines) can DevOps detect unexpected situations that require escalation to human ?
- What are the resource limitations (CPU, RAM) expected for this service ?
- Are all relevant variables documented and adjustable via environment variables (i.e. no hardcoded magic numbers) ?
-->
