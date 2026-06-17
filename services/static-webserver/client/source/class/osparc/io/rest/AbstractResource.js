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
  },

  construct: function(description) {
    this.base(arguments, description);

    this.configureRequest(function(request, action, params, data) {
      let headers = [{
        key: "Accept",
        value: "application/json"
      }];

      headers.forEach(function(item, index, array) {
        request.setRequestHeader(item.key, item.value);
      });
    });
  },

  members:{
    /**
     * Default implementation
     * Can be overridden in subclass to change prefix
     */
    formatUrl: function(tail) {
      return osparc.io.rest.AbstractResource.API + tail;
    }
  }
});
