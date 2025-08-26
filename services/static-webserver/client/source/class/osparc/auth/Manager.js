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

  events: {
    "loggedOut": "qx.event.type.Event"
  },

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

    updatePhoneNumber: function(newPhoneNumber) {
      const params = {
        data: {
          phone: newPhoneNumber
        }
      };
      return osparc.data.Resources.fetch("profile", "phoneRegister", params);
    },

    validateCodeUpdatePhone: function(code, loginCbk, failCbk, context) {
      const params = {
        data: {
          code
        }
      };
      osparc.data.Resources.fetch("profile", "phoneConfirm", params)
        .then(data => {
          loginCbk.call(context, data);
        })
        .catch(err => failCbk.call(context, err.message));
    },

    isLoggedIn: function() {
      return osparc.auth.Data.getInstance().isLoggedIn();
    },

    /*
     * Function that checks if there is a token and validates it against the server.
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

    login: function(email, password) {
      return new Promise((resolve, reject) => {
        const params = {
          email,
          password
        };
        const url = osparc.data.Resources.resources["auth"].endpoints["postLogin"].url;
        const xhr = new XMLHttpRequest();
        xhr.onload = () => {
          const resp = JSON.parse(xhr.responseText);
          if (xhr.status === 202) {
            const data = resp.data;
            const message = osparc.auth.core.Utils.extractMessage(data);
            const retryAfter = osparc.auth.core.Utils.extractRetryAfter(data)
            resolve({
              status: xhr.status,
              message,
              retryAfter,
              nextStep: data["name"]
            });
          } else if (xhr.status === 200) {
            osparc.data.Resources.fetch("profile", "getOne")
              .then(profile => {
                this.__loginUser(profile);
                const data = resp.data;
                const message = osparc.auth.core.Utils.extractMessage(data);
                resolve({
                  status: xhr.status,
                  message
                });
              })
              .catch(err => reject(err));
          } else if (resp.error == null) {
            reject({message: this.tr("Unsuccessful Login")});
          } else {
            reject(resp.error);
          }
        };
        xhr.onerror = err => reject(err);
        xhr.open("POST", url, true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify(params));
      });
    },

    logout: function() {
      const params = {
        data: {
          "client_session_id": osparc.utils.Utils.getClientSessionID()
        }
      };
      const options = {
        timeout: 5000,
        timeoutRetries: 5
      };
      return osparc.data.Resources.fetch("auth", "postLogout", params, options)
        .finally(() => {
          this.__logoutUser();
          this.fireEvent("loggedOut");
        });
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
        username: profile["userName"],
        firstName: profile["first_name"],
        lastName: profile["last_name"],
        expirationDate: profile["expirationDate"] ? new Date(profile["expirationDate"]) : null
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
      const role = profile.role.toLowerCase();
      osparc.data.Permissions.getInstance().setRole(role);
    },

    __logoutUser: function() {
      osparc.auth.Data.getInstance().resetEmail();
      osparc.auth.Data.getInstance().resetToken();
      osparc.store.Store.getInstance().setCurrentStudyId(null);
    }
  }
});
