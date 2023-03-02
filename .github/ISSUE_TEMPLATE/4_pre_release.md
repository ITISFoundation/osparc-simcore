---
name: 🚀 Pre-release to staging (developers-only)
about: Creates an issue to pre-release from master to staging deploy (includes hotfixes)
title: '🚀 Pre-release master -> staging_SPRINTNAME_VERSION (DATE)'
labels: 'release'
assignees: 'pcrespov'
---

TODO: create release label

In preparation for [pre-release](https://github.com/ITISFoundation/osparc-simcore/releases). Here an initial (incomplete) list of tasks to prepare before pre-releasing:


- [ ] Draft changelog from commits list (see [docs/releasing-workflow-instructions.md](https://github.com/ITISFoundation/osparc-simcore/blob/6cae77e5444f825f67fca65876922c8d26901fd2/docs/releasing-workflow-instructions.md))
- [ ] Check important changes 🚨
- [ ] Devops check (⚠️ devops)
- [ ] e2e testing check
- [ ] Summary
- [ ] Release
- [ ] Postmortem

---
# Motivation:

<!-- Staging is an intermediate environment between development (master) and production that allows us to test in isolation changes in the framework.
In addition, the pre-release workflow shall be used as a simulation to production that can help us to anticipate changes and mitigate failures.

- Explain what motivates this pre-release?
- Which important changes we might pay attention to?
- How should we test them?
- Is there anything in particular we should monitor?
-->



#  Devops check (⚠️ devops)
<!-- The goal here is to analyze the PRs marked with (⚠️ devops).  We should determine and prepare necessary changes required in the environments configs.

This procedure should be taken also as an exercise in preparation for the release to production as well.
 -->


# e2e testing check
<!-- Check that e2e in master: are there any major known issues?

Keep an agenda of what has been reported on every daily
-->
- Mon. ...
- Tue.
- Wed.
- Thu.
- Fri.


# [Commits (in order)](https://github.com/ITISFoundation/osparc-simcore/commits/master)
<!-- Is there anything in particular we should monitor?

- Mark commits with 🚨 to warn about possible issues. Contact PR creator to understand how to test/target
- Mark all the commits that were already cherry picked from master a hotfix as [ 📌  ``staging_switzer_5``]
-->




# Summary
<!-- Adapt

  - sprint_name
  - version
  - commit_sha
  - start
  - stop
-->

- [ ] `` make release-staging name=ResistanceIsFutile version=9 git_sha=7d9dcc313f9ced0bd1e6508363148841683b6d7c``
- [ ] Draft [pre-release](https://github.com/ITISFoundation/osparc-simcore/releases)
- [ ] Check [target commit 7d9dcc313f9ced0bd1e6508363148841683b6d7c](https://github.com/ITISFoundation/osparc-simcore/commits/master)  ✅ CI passed
- [ ] Announce
```json
{"start": "2023-02-01T12:30:00.000Z", "end": "2023-02-01T13:00:00.000Z", "reason": "Release ResistanceIsFutile9 "}
```


# Release

- [ ] Release (release draft)
- [ ] Check Release CI
- [ ] Check deployed dalco/aws ()
- [ ] Delete announcement
- [ ] Check e2e runs
- [ ] Announce
``` md
https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_ResistanceIsFutile10
```
