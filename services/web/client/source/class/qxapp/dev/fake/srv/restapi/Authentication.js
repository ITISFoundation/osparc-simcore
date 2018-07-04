/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.dev.fake.srv.restapi.Authentication", {
  type: "static",

  statics: {
    REMEMBER: false,

    mockData: [{
      method: "GET",
      url: "api/v1.0/token",
      response: function(request) {
        console.log("Received request:", request);

        // Defaults unauthorized
        let status = 401;
        let headers = {
          "Content-Type": "application/json"
        };
        let body = null;

        const login = qx.lang.Json.parse(request.requestBody);
        // TODO: validate json!

        const userId = qxapp.dev.fake.srv.restapi.Authentication.checkCredentials(login);
        if (userId !== null) {
          status = 200;
          body = {
            token: qxapp.dev.fake.srv.restapi.Authentication.createToken(userId)
          };
        }

        request.respond(status, headers, qx.lang.Json.stringify(body));
      }
    }],

    createToken: function(userId, expiration=24) {
      return "this-is-a-dummy-token-that-expires-in-" + String(expiration) + "hours-for-" + String(userId);
    },

    getUserIdFromToken: function(token) {
      if (token.startsWith("this-is-a-dummy-token-that-expires-in-")) {
        var parts = token.split("-");
        return parts.pop();
      }
      return null;
    },

    checkCredentials: function(login) {
      var userId = qxapp.dev.fake.srv.db.User.DUMMYNAMES.findIndex(function(userName, userIndex) {
        const validEmail = qxapp.dev.fake.srv.db.User.getEmail(userIndex);
        return validEmail == login.email && login.password == "z43";
      });
      return userId>=0? userId: null;
    },

    /**
     * Gets {email, password} from header
     * produced by qx.io.request.authentication.Basic
    */
    decodeAuthHeader: function(requestHeaders) {
      var res = {
        email: null,
        password: null
      };
      var header = requestHeaders["Authorization"];

      // Remove 'Basic $value'
      var value = header.split(" ")[1];
      // parse '$username : $password'
      var pair = qx.util.Base64.decode(value).split(":");
      res["email"] = pair[0];
      res["password"] = pair[1];

      return res;
    },

    /**
     * Parse {email:, password:} object extracting
     * parameters from body
     *
    */
    parseLoginParameters: function(requestBody) {
      var res = {
        email: null,
        password: null
      };

      var vars = requestBody.split("&");
      for (var i = 0; i < vars.length; ++i) {
        var pair = vars[i].split("=");
        res[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
      }
      return res;
    }
  },

  defer: function(mystatics) {
    if (qx.core.Environment.get("dev.enableFakeSrv")) {
      console.debug("REST API Authentication enabled");
      qx.dev.FakeServer.getInstance().configure(mystatics.mockData);
    }
  }

});
