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
qx.Class.define("osparc.io.rest.AbstractResource", {
  extend: qx.io.rest.Resource,
  type: "abstract",

  statics: {
    API: "/v0",
    AUTHENTICATION: null,

    setAutheticationHeader: function(usernameOrToken, password=null) {
      osparc.io.rest.AbstractResource.AUTHENTICATION = new qx.io.request.authentication.Basic(usernameOrToken, password);
    }

  },

  construct: function(description) {
    this.base(arguments, description);

    this.configureRequest(function(request, action, params, data) {
      let headers = [{
        key: "Accept",
        value: "application/json"
      }];

      const auth = osparc.io.rest.AbstractResource.AUTHENTICATION;
      if (auth === null) {
        console.debug("Authentication missing");
      } else {
        headers.concat(auth.getAuthHeaders());
      }

      headers.forEach(function(item, index, array) {
        request.setRequestHeader(item.key, item.value);
      });
    });
  },

  members:{

    /**
     * Default implementation
     * Can be overriden in subclass to change prefix
     */
    formatUrl: function(tail) {
      return osparc.io.rest.AbstractResource.API + tail;
    }
  }



});
