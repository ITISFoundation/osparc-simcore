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
    register: function(userData) {
      const params = {
        data: userData
      };
      return osparc.data.Resources.fetch("auth", "postRegister", params);
    },

    verifyPhoneNumber: function(email, phoneNumber) {
      const params = {
        data: {
          email,
          phone: phoneNumber
        }
      };
      return osparc.data.Resources.fetch("auth", "postVerifyPhoneNumber", params)
    },

    validateCodeRegister: function(email, code) {
      const params = {
        data: {
          email,
          code
        }
      };
      osparc.data.Resources.fetch("auth", "postValidationCodeRegister", params)
        .then(data => {
          console.log(data);
        })
        .catch(err => console.error(err.message));
    },

    isLoggedIn: function() {
      // TODO: how to store this localy?? See http://www.qooxdoo.org/devel/pages/data_binding/stores.html#offline-store
      // TODO: check if expired??
      // TODO: request server if token is still valid (e.g. expired, etc)
      const auth = osparc.auth.Data.getInstance().getAuth();
      return auth !== null && auth instanceof osparc.io.request.authentication.Token;
    },

    /*
     * Function that checks if there is a token and validates it aginst the server.
     */
    validateToken: function() {
      return new Promise((resolve, reject) => {
        if (osparc.auth.Data.getInstance().isLogout()) {
          reject("User not logged in");
        } else {
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(profile => {
              this.__loginUser(profile);
              resolve(profile);
            })
            .catch(err => {
              reject(err);
            });
        }
      });
    },

    login: function(email, password, loginCbk, twoFactoAuthCbk, failCbk, context) {
      const params = {
        data: {
          email,
          password
        }
      };
      osparc.data.Resources.fetch("auth", "postLogin", params)
        .then(data => {
          // FIXME OM: check status is 202
          if ("message" in data && data.message.includes("SMS")) {
            twoFactoAuthCbk.call(context, data);
          } else {
            osparc.data.Resources.getOne("profile", {}, null, false)
              .then(profile => {
                this.__loginUser(profile);
                loginCbk.call(context, data);
              })
              .catch(err => failCbk.call(context, err.message));
          }
        })
        .catch(err => failCbk.call(context, err.message));
    },

    validateCodeLogin: function(email, code, loginCbk, failCbk, context) {
      const params = {
        data: {
          email,
          code
        }
      };
      osparc.data.Resources.fetch("auth", "postValidationCodeLogin", params)
        .then(data => {
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(profile => {
              this.__loginUser(profile);
              loginCbk.call(context, data);
            })
            .catch(err => failCbk.call(context, err.message));
        })
        .catch(err => failCbk.call(context, err.message));
    },

    logout: function() {
      const params = {
        data: {
          "client_session_id": osparc.utils.Utils.getClientSessionID()
        }
      };
      osparc.data.Resources.fetch("auth", "postLogout", params)
        .then(data => {
          this.fireEvent("logout");
        })
        .catch(error => console.log("already logged out"))
        .finally(this.__logoutUser());
    },

    resetPasswordRequest: function(email, successCbk, failCbk, context) {
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

    __loginUser: function(profile) {
      osparc.auth.Data.getInstance().setEmail(profile.login);
      osparc.auth.Data.getInstance().setToken(profile.login);
      osparc.auth.Data.getInstance().setUserId(profile.id);
      osparc.auth.Data.getInstance().setGroupId(profile["groups"]["me"]["gid"]);
      if ("organizations" in profile["groups"]) {
        const orgIds = [];
        profile["groups"]["organizations"].forEach(org => orgIds.push(org["gid"]));
        osparc.auth.Data.getInstance().setOrgIds(orgIds);
      }
      const role = profile.role.toLowerCase();
      osparc.data.Permissions.getInstance().setRole(role);

      this.__fetchStartUpResources();
    },

    __fetchStartUpResources: function() {
      osparc.data.Resources.get("clusters");
    },

    __logoutUser: function() {
      osparc.auth.Data.getInstance().resetEmail();
      osparc.auth.Data.getInstance().resetToken();
      osparc.store.Store.getInstance().setCurrentStudyId(null);
    }
  }
});
