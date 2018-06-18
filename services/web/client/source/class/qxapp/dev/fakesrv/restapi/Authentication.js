
qx.Class.define("qxapp.dev.fakesrv.restapi.Authentication", {
  type: "static",

  statics: {
    mockData: [{
      method: "POST",
      url: "api/v1/login",
      response: function(request) {
        let status = 401; // Unauthorized
        let headers = {
          "Content-Type": "application/json"
        };
        let body = null;

        const login = qx.lang.Json.parse(request.requestBody);
        //TODO: validate json!

        // if login.user exists:
        //  if verified:
        //    if valid login.password:
        //      if suceeds:
        //        return token

        if (login.username=="bizzy" && login.password=="z43") {
          status = 200;
          body = qx.lang.Json.stringify({
            userId: 0,
            token: "1234"
          });
        }

        request.respond(status, headers, body);
      }
    }]
  },

  defer: function(mystatics) {
    if (qx.core.Environment.get("dev.enableFakeSrv")) {
      console.debug("REST API Authentication enabled");
      qx.dev.FakeServer.getInstance().configure(mystatics.mockData);
    }
  }

});
