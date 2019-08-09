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

/**
 * Base class for RESTful resources
 */
qx.Class.define("qxapp.io.rest.Resource", {
  extend: qx.io.rest.Resource,

  statics: {
    AUTHENTICATION: null,

    setAutheticationHeader: function(usernameOrToken, password=null) {
      qxapp.io.rest.Resource.AUTHENTICATION = new qx.io.request.authentication.Basic(usernameOrToken, password);
    }
  },

  construct: function(description) {
    this.base(arguments, description);

    this.configureRequest(function(request, action, params, data) {
      let headers = [{
        key: "Accept",
        value: "application/json"
      }];

      if (this.AUTHENTICATION !== undefined && this.AUTHENTICATION !== null) {
        headers.concat(this.AUTHENTICATION.getAuthHeaders());
      }

      headers.forEach(function(item, index, array) {
        request.setRequestHeader(item.key, item.value);
      });

      request.setRequestHeader("Content-Type", "application/json");
    });
  }
});
