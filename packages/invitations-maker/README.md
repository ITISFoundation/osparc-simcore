# osparc invitations-maker

``invitations-maker`` can create invitations via CLI or can run as a web app with a http API to create invitations.


A simple workflow would be


1. create ``.env`` file
```
$ invitations-maker generate-dotenv > .env
```
and modify the ``.env`` if needed
2. create a invitation for ``guest@company.com`` as
```
$ invitations-maker invite guest@company.com --issuer=me
```
and will produce a link
3. or start it as a web app as
```
# invitations-maker serve
```
and then open http://127.0.0.1:8000/doc
