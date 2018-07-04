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

      if (this.AUTHENTICATION !== null) {
        headers.concat(this.AUTHENTICATION.getAuthHeaders());
      }

      headers.forEach(function(item, index, array) {
        request.setRequestHeader(item.key, item.value);
      });
    });
  }
});
