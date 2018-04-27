# web-client

``qxapp`` is the main client-side application of the sim-core platform.


To ease development, we have encapsulated the [qx]-compiler and all setup needed to run the client in a docker container. The docker-compose files in place help running ``qxapp`` stand-alone using a dev server in [qx]. This is a common workflow:

```bash
cd /.../web-client

# 1. the first time you checkout, you need to pull qx contribution packages
docker-compose -f docker-compose.yml -f docker-compose.init.yml run qx

# 2. runs 'qx serve' which serves a website in http://localhost:8080/.
#    Changes in your code will automatically be compiled and updated in the web.
docker-compose up

# 3. close down
docker-compose down
```

[qx]:http://www.qooxdoo.org/
