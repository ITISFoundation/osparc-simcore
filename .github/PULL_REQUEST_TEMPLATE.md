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


or from https://gitmoji.dev/
-->

## What do these changes do?



## Related issue/s

<!-- Link pull request to an issue
  SEE https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue

- resolves ITISFoundation/osparc-issues#428
- fixes #26
-->


## How to test

<!-- Give REVIEWERS some hits or code snippets on how could this be tested -->

## DevOps Checklist
<!--

Some checks that might help your code run stable on production, and help devops assess criticality.

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

<!---
Have you though about the CIA triad?

1. Confidentiality: ensures that information is accessible only to authorized individuals or entities. It involves measures to prevent unauthorized disclosure, access, or use of sensitive data. Confidentiality can be maintained through mechanisms such as encryption, access controls, and secure communication channels.

2.Integrity: Integrity ensures that information remains accurate, complete, and unaltered throughout its lifecycle. It involves protecting data from unauthorized modification, deletion, or tampering. Maintaining data integrity is crucial for ensuring the trustworthiness and reliability of information. Techniques like checksums, digital signatures, and access controls can help enforce data integrity.

3. Availability: Availability ensures that information and resources are accessible and usable when needed. It involves ensuring that authorized users can access information without disruption or delay. Measures to maintain availability include redundancy, fault tolerance, backup systems, and disaster recovery plans. By ensuring availability, organizations can minimize downtime and ensure continuity of operations.

-->

I attest that this PR does not break:

- [ ] Confidentiality
- [ ] Integrity
- [ ] Availability
