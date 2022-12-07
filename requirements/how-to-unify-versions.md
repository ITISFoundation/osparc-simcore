## Package version dispersion

The same package listed in different requirements should have as similar version as possible througout the repository.

Different versions of the same package is denoted here as *dispersion*.

Dispersion can be monitored in the tables created after ugprades using ``requirements/tools/check_changes.py`` or simply
``cmd
make devenv
source .venv/bin/activate
cd requirements/tools
make report
code report.ignore.md
```

## Example

For instance, in this table (a part taken from ``upgrade-report.ignore.md``) we see that some packages have multiple versions across requirements.

| #   | name              | versions-base                   | versions-test                   | versions-tool              |
| --- | ----------------- | ------------------------------- | ------------------------------- | -------------------------- |
| 21  | alembic           | 1.7.4, 1.7.5, 1.7.7             | 1.7.4, 1.7.5, 1.7.7             |                            |
| 45  | certifi           | 2020.12.5, 2021.5.30, 2021.10.8 | 2020.12.5, 2021.5.30, 2021.10.8 |                            |
| 52  | click             | 8.0.3, 8.0.4, 8.1.2, 8.1.3      | 8.0.3, 8.0.4, 8.1.3             | 8.0.3, 8.0.4, 8.1.2, 8.1.3 |
| 77  | email-validator   | 1.1.1, 1.1.2, 1.1.3, 1.2.1      | 1.2.1                           |                            |
| 159 | orjson            | 3.4.8, 3.5.4, 3.6.7, 3.6.8      |                                 |                            |
| 160 | packaging         | 20.4, 20.9, 21.0, 21.3          | 20.4, 20.9, 21.0, 21.3          |                            |
| 179 | prometheus-client | 0.11.0, 0.13.1, 0.14.1          |                                 |                            |
| 182 | psycopg2-binary   | 2.8.6, 2.9.1, 2.9.2, 2.9.3      | 2.8.6, 2.9.2, 2.9.3             |                            |
| 197 | pyparsing         | 2.4.7, 3.0.7, 3.0.8, 3.0.9      | 2.4.7, 3.0.7, 3.0.8, 3.0.9      |                            |
| 198 | pyrsistent        | 0.17.3, 0.18.0, 0.18.1          | 0.18.1                          |                            |
| 215 | python-dotenv     | 0.15.0, 0.18.0, 0.19.0, 0.20.0  | 0.15.0, 0.18.0, 0.19.0, 0.20.0  |                            |
| 225 | requests          | 2.25.1, 2.26.0, 2.27.1          | 2.25.1, 2.26.0, 2.27.1          |                            |
| 242 | sqlalchemy        | 1.4.31, 1.4.32, 1.4.36          | 1.4.31, 1.4.32, 1.4.36          |                            |


in order to unify the versions, we can upgrade each of them individually in batch as follows

```bash

packages=orjson,packaging,prometheus-client,psycopg2-binary,pyparsing,pyrsistent,python-dotenv,requests # ... and many more

for u in ${packages//,/ }
do
   make reqs-all upgrade=$u &> reqs-$u.log
   git commit -am "upgrades $u" --no-verify
done
```

It would also be possible to upgrade them simultaneously by using ``--upgrade`` multiple times as ``pip-compile --upgrade X --upgrade Y ...``
but we prefer to do it one by one and commit changes so that any issue can be tracked to the library upgrade


TIP: Check the **Repo-wide overview of libraries** table in the report. Observe the libraries with multiple version in ``version-*`` columns. Note that we can use the script to unifyunify:
  - Those with no ``version-base`` and multiple in ``version-test``
  - Thos with multiple in ``version-base`` and non in ``version-test``
