# Devops checklist

- No ENV changes or I properly updated ENV ([read the instruction](https://git.speag.com/oSparc/osparc-ops-deployment-configuration/-/blob/configs/README.md?ref_type=heads#how-to-update-env-variables))

- Some checks that might help your code run stable on production, and help devops assess criticality.
  - How can DevOps check the health of the service ?
  - How can DevOps safely and gracefully restart the service ?
  - How and why would this code fail ?
  - What kind of metrics are you exposing ?
  - Is there any documentation/design specification for the service ?
  - How (e.g. through which loglines) can DevOps detect unexpected situations that require escalation to human ?
  - What are the resource limitations (CPU, RAM) expected for this service ?
  - Are all relevant variables documented and adjustable via environment variables (i.e. no hardcoded magic numbers) ?

Ref: Modified from https://oschvr.com/posts/what-id-like-as-sre/
