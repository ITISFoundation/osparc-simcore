
/** Authentication Manager
 *
 *  - Entrypoint to perform authentication requests with backend
 *  - Keeps state of current application
 *  - Keeps authentication header for future requests to the backend
*/
qx.Class.define("qxapp.auth.Manager", {
  extend: qx.core.Object,
  type: "singleton",

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events: {
    "logout" : "qx.event.type.Event"
  },


  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members:{
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

    login: function(email, pass, callback, context) {
      //---------------------------------------------------------------------------
      // TODO: temporarily will allow any user until issue #162 is resolved and/or python server has active API
      if (!qx.core.Environment.get("dev.enableFakeSrv")) {
        this.setToken("fake-token");
        callback.call(context, true);
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
        callback.call(context, true, null);
      }, this);

      request.addListener("fail", function(e) {
        // TODO: why if failed? Add server response message
        callback.call(context, false, "Authentication failed");
      }, this);

      request.send();
    },

    logout: function() {
      this.resetToken();
      this.fireEvent("logout");
    },

    resetPassword: function(email, callback, context) {
      console.debug("Resetting password ...");

      // TODO: request server
      let success = true;
      let msg = "An email has been sent to you.";
      callback.call(context, success, msg);
    },

    register: function(userData, callback, context) {
      console.debug("Registering user ...");

      // TODO: request server
      let success = true;
      let msg = "User has been registered. A confirmation email has been sent to you.";
      callback.call(context, success, msg);
    }
  }
});
