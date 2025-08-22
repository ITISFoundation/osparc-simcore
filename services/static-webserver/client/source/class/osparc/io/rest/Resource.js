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

/**
 * Base class for RESTful resources
 */
qx.Class.define("osparc.io.rest.Resource", {
  extend: qx.io.rest.Resource,

  construct: function(description, timeout = 0) {
    this.base(arguments, description);

    this.configureRequest(request => {
      const headers = [{
        key: "Accept",
        value: "application/json"
      }, {
        key: "Content-Type",
        value: "application/json"
      }, {
        key: "X-Simcore-Products-Name",
        value: qx.core.Environment.get("product.name")
      }, {
        key: "X-Client-Session-Id",
        value: osparc.utils.Utils.getClientSessionID()
      }];

      if (this.AUTHENTICATION !== undefined && this.AUTHENTICATION !== null) {
        headers.concat(this.AUTHENTICATION.getAuthHeaders());
      }

      headers.forEach(item => request.setRequestHeader(item.key, item.value));

      if (timeout) {
        request.setTimeout(timeout);
      }
    });
  },

  statics: {
    AUTHENTICATION: null,

    setAutheticationHeader: function(usernameOrToken, password=null) {
      osparc.io.rest.Resource.AUTHENTICATION = new qx.io.request.authentication.Basic(usernameOrToken, password);
    }
  },

  members: {
    includesRoute: function(route) {
      return Object.keys(this.__routes).includes(route);
    }
  }
});
