/* eslint no-warning-comments: "off" */
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
        // TODO: validate json!

        // if login.user exists:
        //  if verified:
        //    if valid login.password:
        //      if suceeds:
        //        return token

        const DUMMY_EMAIL = "bizzy@itis.ethz.ch";
        const DUMMY_PASS = "z43";
        const DUMMY_USERID = 1;
        const DUMMY_USERTOKEN = "eeeaee5e-9b6e-475b-abeb-66a000be8d03";

        if (login.username == DUMMY_EMAIL && login.password == DUMMY_PASS) {
          status = 200;
          body = qx.lang.Json.stringify({
            userId: DUMMY_USERID,
            token: DUMMY_USERTOKEN
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
