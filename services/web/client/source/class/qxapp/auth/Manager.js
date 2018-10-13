
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
      // FIXME: temporarily will allow any user until issue #162 is resolved and/or python server has active API
      //if (!qx.core.Environment.get("dev.enableFakeSrv")) {
      //  this.setToken("fake-token");
      //  callback.call(context, true);
      //  return;
      //}
      //---------------------------------------------------------------------------

      let request = new qx.io.request.Xhr();
      const prefix = qxapp.io.rest.AbstractResource.API;
      request.set({
        authentication: new qx.io.request.authentication.Basic(email, pass),
        url: prefix + "/",
        method: "GET"
      });

      request.addListener("success", function(e) {
        // Completes without error and *transport status indicates success*
        let req = e.getTarget();
        console.debug("Login suceeded:", "status  :", req.getStatus(), "phase   :", req.getPhase(), "response: ", req.getResponse());
        this.assert(req == request);

        let hasLoggedIn = false;
        let msg = null;

        // enveloped, error extraction from payload
        const {data, error} = req.getResponse();

        if (error) {
          msg = this._createErrorMessage(error.errors.logs);
        } else {
          // TODO: validate data against specs

          this.setToken(data.token);
          hasLoggedIn = true;
        }

        callback.call(context, hasLoggedIn, msg);
      }, this);

      request.addListener("fail", function(e) {
        let req = e.getTarget();
        const msg = this._createErrorMessage(req.error) | "Authentication failed";

        callback.call(context, false, msg);
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
    },

    _createErrorMessage: function(logs) {
      // Adds server response to error message

      let msg = null;
      if (logs) {
        // TODO: improve error logging
        for (let i=0; i<logs.length; ++i) {
          const log = logs[i];
          if (log.level=="ERROR") {
            msg = log.message;
            break;
          } else {
            console.debug(logs[i]);
          }
        }
      }
      return msg;
    }

  }
});
