/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/** Authentication Manager
 *
 *  - Entrypoint to perform authentication requests with backend
 *  - Keeps state of current application
 *  - Keeps authentication header for future requests to the backend
*/
/* eslint no-warning-comments: "off" */
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

    isLoggedIn: function() {
      // TODO: how to store this localy?? See http://www.qooxdoo.org/devel/pages/data_binding/stores.html#offline-store
      // TODO: check if expired??
      // TODO: request server if token is still valid (e.g. expired, etc)
      const auth = qxapp.auth.Data.getInstance().getAuth();
      return auth !== null && auth instanceof qx.io.request.authentication.Basic;
    },

    login: function(email, pass, successCbk, failCbk, context) {
      // TODO: consider qx.promise instead of having two callbacks and a context might be nicer to work with

      let request = new qxapp.io.request.ApiRequest("/auth/login", "POST");
      request.set({
        authentication: new qx.io.request.authentication.Basic(email, pass),
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
        // TODO: activate tokens!?
        this.__loginUser(email, data.token || "fake token");
        successCbk.call(context, data);
      }, this);

      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    logout: function() {
      this.__logoutUser();
      this.fireEvent("logout");
    },

    register: function(userData, successCbk, failCbk, context) {
      console.debug("Registering user ...");
      // api/specs/webserver/v0/openapi-auth.yaml
      let request = new qxapp.io.request.ApiRequest("/auth/register", "POST");
      request.set({
        requestData: userData
      });

      this.__bindDefaultSuccessCallback(request, successCbk, context);
      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    resetPasswordRequest: function(email, successCbk, failCbk, context) {
      console.debug("Requesting reset password ...");
      // api/specs/webserver/v0/openapi-auth.yaml
      let request = new qxapp.io.request.ApiRequest("/auth/reset-password", "POST");
      request.set({
        requestData: {
          "email": email
        }
      });

      this.__bindDefaultSuccessCallback(request, successCbk, context);
      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    resetPassword: function(newPassword, confirmation, code, successCbk, failCbk, context) {
      console.debug("Reseting password ...");
      // api/specs/webserver/v0/openapi-auth.yaml
      let request = new qxapp.io.request.ApiRequest("/auth/reset-password/" + encodeURIComponent(code), "POST");
      request.setRequestData({
        password: newPassword,
        confirm: confirmation
      });

      this.__bindDefaultSuccessCallback(request, successCbk, context);
      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    evalPasswordStrength: function(password, callback, context=null) {
      let request = new qxapp.io.request.ApiRequest("/auth/check-password/" + encodeURIComponent(password), "GET");
      request.addListener("success", evt => {
        let payload = evt.getTarget().getResponse();
        callback.call(context, payload.strength, payload.rating, payload.improvements);
      }, this);

      request.send();
    },

    __loginUser: function(email, token) {
      qxapp.auth.Data.getInstance().setToken(token);
      qxapp.auth.Data.getInstance().setEmail(email);
    },

    __logoutUser: function() {
      qxapp.auth.Data.getInstance().resetToken();
      qxapp.auth.Data.getInstance().resetEmail();
    },

    __bindDefaultSuccessCallback: function(request, successCbk, context) {
      request.addListener("success", function(e) {
        const {
          data
        } = e.getTarget().getResponse();

        // TODO: validate data against specs???
        // FIXME: Data is an object
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
        // FIXME: Data is an object
        failCbk.call(context, msg);
      }, this);
    }
  }
});
