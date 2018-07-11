
/** Authentication Manager
 *
 *  - Entrypoint to perform authentication requests with backend
 *  - Keeps authentication token
*/
qx.Class.define("qxapp.auth.Manager", {
  extend: qx.core.Object,
  type: "singleton",
  events:{
    "login": "qx.event.type.Data"
  },
  members:
  {
    __auth: null,

    setToken: function(token) {
      // Keeps token for future requests
      const auth = new qx.io.request.authentication.Basic(token, null);
      this.__auth = auth;
    },

    resetToken: function() {
      this.__auth = null;
    },

    isLoggedIn: function() {
      // TODO: how to store this localy?? See http://www.qooxdoo.org/devel/pages/data_binding/stores.html#offline-store
      // TODO: check if expired??
      // TODO: request server if token is still valid (e.g. expired, etc)
      return this.__auth !== null && this.__auth instanceof qx.io.request.authentication.Basic;
    },

    login: function(email, pass) {
      //---------------------------------------------------------------------------
      // TODO: temporarily will allow any user until issue #162 is resolved and/or python server has active API
      if (!qx.core.Environment.get("dev.enableFakeSrv")) {
        this.setToken("fake-token");
        this.fireDataEvent("login", true);
        return;
      }
      //---------------------------------------------------------------------------


      let request = new qx.io.request.Xhr();
      const prefix = qxapp.io.rest.AbstractResource.API;
      request.set({
        authentication: new qx.io.request.authentication.Basic(email, pass),
        url: prefix + "/token",
        method: "GET"
      });

      request.addListener("success", function(e) {
        // Completes without error and *transport status indicates success*
        let req = e.getTarget();
        console.debug("Login suceeded:", "status  :", req.getStatus(), "phase   :", req.getPhase(), "response: ", req.getResponse());
        this.assert(req == request);

        this.setToken(req.getResponse().token);
        this.fireDataEvent("login", true);
      }, this);

      request.addListener("fail", function(e) {
        // TODO: why if failed? Add server resposne message
        this.fireDataEvent("login", false);
      }, this);

      request.send();
    },

    logout: function() {
      this.resetToken();
    }

  }
});
