
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

    login: function(email, pass, successCbk, failCbk, context) {
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
        // authentication: new qx.io.request.authentication.Basic(email, pass), // FIXME: remove from here
        requestData: {
          "email": email,
          "password": pass
        }
      });

      request.addListener("success", function(e) {
        const {
          data
        } = e.getTarget().getResponse();

        // TODO: validate data against specs???
        this.setToken(data.token);
        successCbk.call(context, data.message);
      }, this);

      this.__bindDefaultFailCallback(request, failCbk, context);

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

    register: function(userData, successCbk, failCbk, context) {
      console.debug("Registering user ...");

      let request = new qxapp.io.request.ApiRequest("/auth/register", "POST");
      request.set({
        requestData: userData
      });

      this.__bindDefaultSuccessCallback(request, successCbk, context);
      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },



    __bindDefaultSuccessCallback: function(request, successCbk, context) {
      request.addListener("success", function(e) {
        const {
          data
        } = e.getTarget().getResponse();

        // TODO: validate data against specs???
        successCbk.call(context, data);
      }, this);
    },

    __bindDefaultFailCallback: function(request, failCbk, context) {
      request.addListener("fail", function(e) {
        const {
          error
        } = e.getTarget().getResponse();

        let msg = "";
        if (error) {
          for (var i=0; i<error.errors.length; i++) {
            msg = msg + error.errors[i].message + " ";
          }
        }

        failCbk.call(context, msg);
      }, this);
    }


  }
});
