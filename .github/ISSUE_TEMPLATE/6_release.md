---
name: 🚀 Release to production  (developers-only)
about: Creates an issue to release from staging to production
title: '🚀 Release vX.X.0'
labels: 'release'
assignees: 'pcrespov'

---
In preparation for [release](https://github.com/ITISFoundation/osparc-simcore/releases). Here an initial (incomplete) list of tasks to prepare before releasing:


- [ ] Prepare staging
- [ ] Check changelog 🚨
- [ ] Check devops ⚠️
- [ ] Test assessment: e2e-testing
- [ ] Test assessment: targeted-testing
- [ ] Test assessment: user-testing ✅
- [ ] Summary
- [ ] Release

---
# Motivation
<!--
- Pre-release and hotfix until stable
- Keep "motivation" as concrete as possible
- ...
-->

# Check changelog 🚨
<!--
- draft changelogs accumulated from staging
- human-readable highlights (optional)
-->


# Check devops ⚠️
<!-- review and prepare (⚠️ devops)
	- assess whether announcement necessary (e.g. logout?)
	- assess when is the most comfortable time to do release
-->

# Test assessment: e2e-testing
 <!-- Assessment carried out by batman/robin based on e2e daily tests outcome
 -->

# Test assessment: targeted-testing ✅
 <!-- Assessment carried out app-team on changelog **at least** on items marked with 🚨. Then replace with ✅ -->


# Test assessment: user-testing
 <!-- save all record zoom session  ``filesrv/osparc/DEVELOPERS/test-sessions`` and
 create an issue to follow up on them. Add issue here!
 -->


# Release summary
<!-- Adapt

  - sprint_name
  - version
  - commit_sha
  - start
  - stop
-->

- [] Prepare
```cmd
make release-prod version=X.X.0  git_sha=7d9dcc313f9ced0bd1e6508363148841683b6d7c
```
- [ ] [**draft** release changelog](https://github.com/ITISFoundation/osparc-simcore/releases)
- [ ] Check [target commit 7d9dcc313f9ced0bd1e6508363148841683b6d7c CI passed](https://github.com/ITISFoundation/osparc-simcore/commits/master)
- [ ] Announce maintenance in **both** status page :
```json
{"start": "2023-02-03T10:00:00.000Z", "end": "2023-02-03T11:00:00.000Z", "reason": "Release vX.X.0 "}
```


# Release assessment

- [ ] Release (release draft)
- [ ] Check CI
- [ ] Check deployed dalco/aws/tip
- [ ] Delete announcement
- [ ] Check e2e runs
- [ ] Announce
``` md
https://github.com/ITISFoundation/osparc-simcore/releases/tag/vX.X.0
```
