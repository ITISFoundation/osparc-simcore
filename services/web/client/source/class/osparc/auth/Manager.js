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
        osparc.data.Resources.getOne("profile", {}, null, false)
          .then(profile => {
            this.__loginUser(profile.login);
            osparc.data.Permissions.getInstance().setRole(profile.role);
            successCb.call(ctx, profile);
          })
          .catch(err => {
            errorCb.call(ctx, err);
          });
      }
    },

    login: function(email, password, successCbk, failCbk, context) {
      const params = {
        data: {
          email,
          password
        }
      };
      osparc.data.Resources.fetch("auth", "postLogin", params)
        .then(data => {
          this.__loginUser(email);
          successCbk.call(context, data);
        })
        .catch(err => failCbk.call(context, err.message));
    },

    logout: function() {
      osparc.data.Resources.fetch("auth", "getLogout");
      this.__logoutUser();
      this.fireEvent("logout");
    },

    register: function(userData, successCbk, failCbk, context) {
      console.debug("Registering user ...");
      const params = {
        data: userData
      };
      osparc.data.Resources.fetch("auth", "postRegister", params)
        .then(data => {
          successCbk.call(context, data);
        })
        .catch(err => failCbk.call(context, err.message));
    },

    resetPasswordRequest: function(email, successCbk, failCbk, context) {
      console.debug("Requesting reset password ...");
      const params = {
        data: {
          email
        }
      };
      osparc.data.Resources.fetch("auth", "postRequestResetPassword", params)
        .then(data => {
          successCbk.call(context, data);
        })
        .catch(err => failCbk.call(context, err.message));
    },

    resetPassword: function(newPassword, confirmation, code, successCbk, failCbk, context) {
      console.debug("Reseting password ...");
      const params = {
        url: {
          code
        },
        data: {
          password: newPassword,
          confirm: confirmation
        }
      };
      osparc.data.Resources.fetch("auth", "postResetPassword", params)
        .then(data => {
          successCbk.call(context, data);
        })
        .catch(err => failCbk.call(context, err.message));
    },

    __loginUser: function(email) {
      osparc.auth.Data.getInstance().setEmail(email);
      osparc.auth.Data.getInstance().setToken(email);
    },

    __logoutUser: function() {
      osparc.auth.Data.getInstance().resetEmail();
      osparc.auth.Data.getInstance().resetToken();
    }
  }
});
