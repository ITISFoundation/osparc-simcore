# Development notes

THIS FILE IS ONLY FOR DEVELOPMENT IN FORK! SHOULD NOT BE INCLUDED IN OFFICIAL REPO


- versioning: see class sys.version_info

- TODO: how to use sessions considering:
  - Requests for the same user might run in different server services
  - Where do states leave
-TODO: add in service/postgres to tools to diagnose the database/init service etc...

pytest.ini is temporary

##

```bash
cd osparc-simcore/services
docker-compose -f docker



 # if fails change
 docker-compose restart

```



## database service

To check database stand-alone check
```bash
 docker-compose up adminer

```
### Issues

- had to remove old volume otherwise it would not recognize user!?  ``docker volume ls && docker volume rm services_postgres``


## Tests

- added pytest.ini




## References

-[[1]] RESTful API Design Tips from Experience by P.Boyer

[1]:https://medium.com/studioarmix/learn-restful-api-design-ideals-c5ec915a430f
