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

    checkInvitation: function(invitation) {
      const params = {
        data: {
          invitation
        }
      };
      return osparc.data.Resources.fetch("auth", "checkInvitation", params);
    },

    verifyPhoneNumber: function(email, phoneNumber) {
      const params = {
        data: {
          email,
          phone: phoneNumber
        }
      };
      return osparc.data.Resources.fetch("auth", "verifyPhoneNumber", params);
    },

    validateCodeRegister: function(email, phone, code, loginCbk, failCbk, context) {
      const params = {
        data: {
          email,
          phone,
          code
        }
      };
      osparc.data.Resources.fetch("auth", "validateCodeRegister", params)
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

    validateCodeLogin: function(email, code, loginCbk, failCbk, context) {
      const params = {
        data: {
          email,
          code
        }
      };
      osparc.data.Resources.fetch("auth", "validateCodeLogin", params)
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

    resendCodeViaSMS: function(email) {
      const params = {
        data: {
          email,
          via: "SMS"
        }
      };
      return osparc.data.Resources.fetch("auth", "resendCode", params);
    },

    resendCodeViaEmail: function(email) {
      const params = {
        data: {
          email,
          via: "Email"
        }
      };
      return osparc.data.Resources.fetch("auth", "resendCode", params);
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

    login: function(email, password, loginCbk, verifyPhoneCbk, twoFactorAuthCbk, failCbk, context) {
      const params = {
        email,
        password
      };
      const url = osparc.data.Resources.resources["auth"].endpoints["postLogin"].url;
      const xhr = new XMLHttpRequest();
      xhr.onload = () => {
        if (xhr.status === 202) {
          const resp = JSON.parse(xhr.responseText);
          const data = resp.data;
          if (data["code"] === "PHONE_NUMBER_REQUIRED") {
            verifyPhoneCbk.call(context);
          } else if (data["code"] === "SMS_CODE_REQUIRED") {
            twoFactorAuthCbk.call(context, data["reason"]);
          }
        } else if (xhr.status === 200) {
          const resp = JSON.parse(xhr.responseText);
          osparc.data.Resources.getOne("profile", {}, null, false)
            .then(profile => {
              this.__loginUser(profile);
              loginCbk.call(context, resp.data);
            })
            .catch(err => failCbk.call(context, err.message));
        } else {
          const resp = JSON.parse(xhr.responseText);
          if ("error" in resp && resp["error"]) {
            failCbk.call(context, resp["error"]["message"]);
          } else {
            failCbk.call(context, this.tr("Login failed"));
          }
        }
      };
      xhr.onerror = () => {
        failCbk.call(context, this.tr("Login failed"));
      };
      xhr.open("POST", url, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.send(JSON.stringify(params));
    },

    logout: function() {
      const params = {
        data: {
          "client_session_id": osparc.utils.Utils.getClientSessionID()
        }
      };
      osparc.data.Resources.fetch("auth", "postLogout", params)
        .then(data => this.fireEvent("logout"))
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

    updateProfile: function(profile) {
      const authData = osparc.auth.Data.getInstance();
      authData.set({
        email: profile["login"],
        firstName: profile["first_name"],
        lastName: profile["last_name"],
        expirationDate: "expirationDate" in profile ? new Date(profile["expirationDate"]) : null
      });
    },

    __loginUser: function(profile) {
      const authData = osparc.auth.Data.getInstance();
      authData.set({
        token: profile.login,
        userId: profile.id,
        groupId: profile["groups"]["me"]["gid"],
        role: profile.role.toLowerCase()
      });
      this.updateProfile(profile);
      if ("organizations" in profile["groups"]) {
        const orgIds = [];
        profile["groups"]["organizations"].forEach(org => orgIds.push(org["gid"]));
        authData.setOrgIds(orgIds);
      }
      const role = profile.role.toLowerCase();
      osparc.data.Permissions.getInstance().setRole(role);

      this.__fetchStartUpResources();
    },

    __fetchStartUpResources: function() {
      const isDisabled = osparc.utils.DisabledPlugins.isClustersDisabled();
      if (isDisabled === false) {
        osparc.data.Resources.get("clusters");
      }
    },

    __logoutUser: function() {
      osparc.auth.Data.getInstance().resetEmail();
      osparc.auth.Data.getInstance().resetToken();
      osparc.store.Store.getInstance().setCurrentStudyId(null);
    }
  }
});
