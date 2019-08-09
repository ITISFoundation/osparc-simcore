/* ************************************************************************

   osparc - the simcore frontend

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

qx.Class.define("osparc.auth.Manager", {
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
      const auth = osparc.auth.Data.getInstance().getAuth();
      return auth !== null && auth instanceof osparc.io.request.authentication.Token;
    },

    /**
     * Function that checks if there is a token and validates it aginst the server. It executes a callback depending on the result.
     *
     * @param {Function} successCb Callback function to be called if the token validation succeeds.
     * @param {Function} errorCb Callback function to be called if the token validation fails or some other error occurs.
     * @param {Object} ctx Context that will be used inside the callback functions (this).
     */
    validateToken: function(successCb, errorCb, ctx) {
      if (osparc.auth.Data.getInstance().isLogout()) {
        errorCb.call(ctx);
      } else {
        const request = new osparc.io.request.ApiRequest("/me", "GET");
        request.addListener("success", e => {
          if (e.getTarget().getResponse().error) {
            errorCb.call(ctx);
          } else {
            this.__loginUser(e.getTarget().getResponse().data.login);
            successCb.call(ctx, e.getTarget().getResponse().data);
          }
        });
        request.addListener("statusError", e => {
          errorCb.call(ctx);
        });
        request.send();
      }
    },

    login: function(email, password, successCbk, failCbk, context) {
      // TODO: consider qx.promise instead of having two callbacks an d a context might be nicer to work with

      let request = new osparc.io.request.ApiRequest("/auth/login", "POST");
      request.set({
        requestData: {
          email,
          password
        }
      });

      request.addListener("success", function(e) {
        const {
          data
        } = e.getTarget().getResponse();

        // TODO: validate data against specs???
        // TODO: activate tokens!?
        this.__loginUser(email);
        successCbk.call(context, data);
      }, this);

      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    logout: function() {
      const request = new osparc.io.request.ApiRequest("/auth/logout", "GET");
      request.send();
      this.__logoutUser();
      this.fireEvent("logout");
    },

    register: function(userData, successCbk, failCbk, context) {
      console.debug("Registering user ...");
      // api/specs/webserver/v0/openapi-auth.yaml
      let request = new osparc.io.request.ApiRequest("/auth/register", "POST");
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
      let request = new osparc.io.request.ApiRequest("/auth/reset-password", "POST");
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
      let request = new osparc.io.request.ApiRequest("/auth/reset-password/" + encodeURIComponent(code), "POST");
      request.setRequestData({
        password: newPassword,
        confirm: confirmation
      });

      this.__bindDefaultSuccessCallback(request, successCbk, context);
      this.__bindDefaultFailCallback(request, failCbk, context);

      request.send();
    },

    evalPasswordStrength: function(password, callback, context=null) {
      let request = new osparc.io.request.ApiRequest("/auth/check-password/" + encodeURIComponent(password), "GET");
      request.addListener("success", evt => {
        let payload = evt.getTarget().getResponse();
        callback.call(context, payload.strength, payload.rating, payload.improvements);
      }, this);

      request.send();
    },

    __loginUser: function(email) {
      osparc.auth.Data.getInstance().setEmail(email);
      osparc.auth.Data.getInstance().setToken(email);
    },

    __logoutUser: function() {
      osparc.auth.Data.getInstance().resetEmail();
      osparc.auth.Data.getInstance().resetToken();
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
