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

        const login = qxapp.dev.fake.srv.restapi.Authentication.decodeAuthHeader(request.requestHeaders);

        const userId = qxapp.dev.fake.srv.restapi.Authentication.checkCredentials(login);
        if (userId !== null) {
          console.debug("User ", qxapp.dev.fake.srv.db.User.DUMMYNAMES[userId], "is logging in ...");
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
        let parts = token.split("-");
        return parts.pop();
      }
      return null;
    },

    checkCredentials: function(login) {
      let userId = qxapp.dev.fake.srv.db.User.DUMMYNAMES.findIndex(function(userName, userIndex) {
        const user = qxapp.dev.fake.srv.db.User.getObject(userIndex);
        return (login.email == user.email || login.email == user.username) && login.password == user.passwordHash;
      });
      return userId>=0? userId: null;
    },

    /**
     * Gets {email, password} from header
     * produced by qx.io.request.authentication.Basic
    */
    decodeAuthHeader: function(requestHeaders) {
      let res = {
        email: null,
        password: null
      };
      let header = requestHeaders["Authorization"];

      // Remove 'Basic $value'
      let value = header.split(" ")[1];
      // parse '$username : $password'
      let pair = qx.util.Base64.decode(value).split(":");
      res.email = pair[0];
      res.password = pair[1];

      return res;
    },

    /**
     * Parse {email:, password:} object extracting
     * parameters from body
     *
    */
    parseLoginParameters: function(requestBody) {
      let res = {
        email: null,
        password: null
      };

      let vars = requestBody.split("&");
      for (let i = 0; i < vars.length; ++i) {
        let pair = vars[i].split("=");
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
