# unit tests

Typical workflow

```shell
cd package_slug
pip install -r requirements/[dev|ci].txt
pytest -v test/unit
```

- **Small**est testing units
- **Isolated**: specific to every package
  - checks functionality of the package under test
  - should run only if changes in code package or requirements are detected
- **Minimal coupling** to other package/services in this repository
  - Fixtures MUST not add any dependency to other services/packages outside of the install requirements
  - Interaction with other modules can be emulated or modified using mockup libraries
  - *Ocassionaly* could use [pytest-docker] for medium size tests but only to deploy services as fixtures ONLY if **external** and **versioned** images are deployed (e.g. [postgres](https://hub.docker.com/_/postgres) or [adminer](https://hub.docker.com/_/adminer) can help to test a part of the package that interacts with a database )
    - Therefore **no need to build** images
  - [pytest-mock] (a pytest plugin on top of [unittest.mock]) is highly encouraged for fixtures
- Using a data-driven criteria to classify tests in [Test Sizes], our unit-tests SHALL include **small** and **medium** sizes:

![tests table](https://cdn-images-1.medium.com/max/800/1*XPhOBPDzVgSn-n8DhW7D8A.png)

## Limitations [by May 2019]

- not time-bounded (e.g. can use time limits in the table above)
- poor coverage [![Coverage Status](https://coveralls.io/repos/github/ITISFoundation/osparc-simcore/badge.svg?branch=master)](https://coveralls.io/github/ITISFoundation/osparc-simcore?branch=master)

## References

- [Unit Testing: Our Tests Are Too Big and Some Ways to Fix Them](https://medium.com/dm03514-tech-blog/unit-testing-our-tests-are-too-big-and-what-we-can-do-about-it-67d100dc424e) by dm03514
- [What the mock? — A cheatsheet for mocking in Python](https://medium.com/@yeraydiazdiaz/what-the-mock-cheatsheet-mocking-in-python-6a71db997832) by Y. Diaz
- [Python unit testing with Pytest and Mock](https://medium.com/@bfortuner/python-unit-testing-with-pytest-and-mock-197499c4623c) by B. Fortuner
- [Test Sizes] by S.Stewards

[unittest.mock]:https://docs.python.org/3/library/unittest.mock.html#module-unittest.mock
[pytest-mock]:https://github.com/pytest-dev/pytest-mock
[pytest-docker]:https://github.com/AndreLouisCaron/pytest-docker
[Test Sizes]:https://testing.googleblog.com/2010/12/test-sizes.html
