/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Class.define("osparc.io.request.authentication.Token", {
  extend: qx.core.Object,

  implement: qx.io.request.authentication.IAuthentication,

  construct: function(token) {
    this.__token = token;
  },

  members: {
    __token: null,

    getAuthHeaders: function() {
      return [{
        key: "Authorization",
        value: "Bearer " + this.__token
      }];
    }
  }
});
