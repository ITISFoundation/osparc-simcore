/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.dev.fake.srv.restapi.User", {
  type: "static",

  statics: {
    mockData: [{
      method: "GET",
      url: "api/v1.0/user/{id}",
      response: function(request) {
        let status = 200; // OK
        let headers = {
          "Content-Type": "application/json"
        };

        let parts = qx.util.StringSplit.split(request.url, "/");
        let userId = parts[parts.length - 1];
        let data = qxapp.dev.fake.srv.db.User.createMock(userId);
        let body = qx.lang.Json.stringify(data);
        request.respond(status, headers, body);
        // FIXME: unite api/v1/uisers
      }
    }, {
      method: "GET",
      url: "api/v1.0/users/",
      response: function(request) {
        let users = qxapp.dev.fake.srv.db.User.DUMMYNAMES;

        let data = [];
        for (let i = 0; i < users.length; i++) {
          data.push({
            id: i,
            username: users[i]
          });
        }
        request.respond(200,
          {
            "Content-Type": "application/json"
          },
          qx.lang.Json.stringify(data));
      }
    }]
  },

  defer: function(mystatics) {
    if (qx.core.Environment.get("dev.enableFakeSrv")) {
      console.debug("REST API enabled");
      qx.dev.FakeServer.getInstance().configure(mystatics.mockData);
    }
  }

});
