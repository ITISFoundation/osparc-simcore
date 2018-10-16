
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
    "logout": "qx.event.type.Event"
  },


  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
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
      // if (!qx.core.Environment.get("dev.enableFakeSrv")) {
      //  this.setToken("fake-token");
      //  callback.call(context, true);
      //  return;
      // }
      //---------------------------------------------------------------------------

      let request = new qxapp.io.request.ApiRequest("/auth/login", "POST");
      request.set({
        authentication: new qx.io.request.authentication.Basic(email, pass), // FIXME: remove from here
        requestData: {
          "email": email,
          "password": pass
        }
      });

      request.addListener("success", function(e) {
        const {
          data,
          error
        } = e.getTarget().getResponse();

        let msg = "Login failed";
        let success = false;

        if (error) {
          // TODO: call isntead callback for "statusError"!
          msg = this.composeMessage(error.logs) || msg; // This should never happen?
          success = false;
        } else {
          // TODO: validate data against specs
          this.setToken(data.token);
          msg = "Login succeeded";
          success = true;
        }
        callback.call(context, success, msg);
      }, this);

      request.addListener("fail", function(e) {
        const {
          error
        } = e.getTarget().getResponse();

        let msg = "Unable to login";
        let success = false;
        if (error) {
          msg = this.composeMessage(error.logs) || "Login failed";
          success = false;
        }
        callback.call(context, success, msg);
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

    composeMessage: function(logs) {
      // Composes a message out of logs array
      let msg = "";
      if (logs) {
        // TODO: improve error logging
        for (let i = 0; i < logs.length; ++i) {
          const log = logs[i];
          if (log.level == "ERROR") {
            msg = log.message;
            break;
          } else {
            console.debug(logs[i]);
          }
        }
      }
      console.debug(msg);
      return msg;
    }

  }
});
