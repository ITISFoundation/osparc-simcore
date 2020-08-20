# Changelog

<!--
FIXME: Compare shows single commit. SEE https://github.com/ITISFoundation/osparc-simcore/issues/1726
-->

## [Unreleased]

<!--------------------------------------------------------->
<!-- ## [0.0.26] - 2020-08-??  TODO: use link and fill entries below -->

### Added

- Started this *human-readable* CHANGELOG
- ``migration`` service that discovers postgres service and upgrades main database (#1714)
- Every group can register official classifiers for studies and services. Diplayed as a tree in UI (#1670, #1719, #1722)

### Changed

- Speedup testing by splitting webserver (#1711)

<!-- ### Deprecated -->
<!-- ### Removed    -->
<!-- ### Fixed      -->
<!-- ### Security   -->

<!--------------------------------------------------------->
## [0.0.25] - 2020-08-04

### Added
- add traefik endpoint to api-gateway (#1555)
- Shared project concurrency (frontend) (#1591)
- Homogenize studies and services (#1569)
- UI Fine grained access - project locking and notification
- Adds support for GPU scheduling of computational services (#1553)

### Changed
- UI/UX improvements (#1657)
- Improving storage performance (#1659)
- Theming (#1656)
- Reduce cardinality of metrics (#1593)

### Fixed
- Platform stability:  (#1645)
- Fix, improves and re-activate e2e CI testing (#1594, #1620, #1631, #1600)
- Fixes defaults (#1640)
- Upgrade storage service (#1585, #1586)
- UPgrade catalog service (#1582)
- Fixes on publish studies handling (#1632)
- Invalidate cache before starting a study (#1602)
- Some enhancements and bug fixes (#1608)
- filter studies by name before deleting them (#1629)
- Bugfix/apiserver does not need sslheaders (#1564)
- fix testing if node has gpu support (#1604)
- /study fails 500 (#1570, #1572)
- fix codecov reports (#1568)

### Security
- Bump yarl from 1.4.2 to 1.5.1 in /packages/postgres-database (#1665)
- Bump ujson from 3.0.0 to 3.1.0 in /packages/service-library (#1664)
- Bump pytest-docker from 0.7.2 to 0.8.0 in /packages/service-library (#1647)
- Bump aiozipkin from 0.6.0 to 0.7.0 in /packages/service-library (#1642)
- Bump lodash from 4.17.15 to 4.17.19 (#1639)
- Maintenance/upgrades test tools (#1628)
- Bugfix/concurent opening projects (#1598)
- Bugfix/allow reading groups anonymous user (#1615)
- Bump docker from 4.2.1 to 4.2.2 in /packages/postgres-database (#1605)
- Bump faker from 4.1.0 to 4.1.1 in /packages/postgres-database (#1573)
- Maintenance/upgrades and tooling (#1546)


---
All notable changes to this service will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the release numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


<!-- Add links below this line ------------------------------------>

[Unreleased]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.25...HEAD
[0.0.25]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.24...v0.0.25
[0.0.24]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.22...v0.0.24
<!-- 0.0.23 was deleted !-->
[0.0.22]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.21...v0.0.22
[0.0.21]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.20...v0.0.21
[0.0.20]:https://github.com/ITISFoundation/osparc-simcore/compare/v0.0.19...v0.0.20
[0.0.19]:https://github.com/ITISFoundation/osparc-simcore/releases/tag/v0.0.19


<!-- HOW TO WRITE  THIS CHANGELOG

- Guiding Principles
  - Changelogs are for humans, not machines.
  - There should be an entry for every single version.
  - The same types of changes should be grouped.
  - Versions and sections should be linkable.
  - The latest version comes first.
  - The release date of each version is displayed.
  - Mention whether you follow Semantic Versioning.

- Types of changes
  - ADDED for new features.
  - CHANGED for changes in existing functionality.
  - DEPRECATED for soon-to-be removed features.
  - REMOVED for now removed features.
  - FIXED for any bug fixes.
  - SECURITY in case of vulnerabilities.

SEE https://keepachangelog.com/en/1.0.0/
-->
