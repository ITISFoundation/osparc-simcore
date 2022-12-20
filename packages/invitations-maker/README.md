# osparc invitations-maker


### Creating an invitation
```cmd

$ export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
$ export INVITATIONS_MAKER_OSPARC_URL=https://myosparc.com

$ invitations-maker invite --email=guest@company.com --issuer=appteam@itis.org
https://myosparc.com/#/registration?invitation=Z0FBQU3TG1FQ0lZbHQtSTA2RVozX3VkU3ZSVU4teVVialptVEpnODZrVzA2d3FTQVdWYU9ScnpZaG1MQm9ISHdYd2M0Sm1HdnBPNEdNVEN1S1ZwSDkwOGNxMTN3PQ%3D%3D
```
