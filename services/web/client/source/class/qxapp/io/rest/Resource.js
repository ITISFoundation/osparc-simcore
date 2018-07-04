/**
 * Base class for RESTful resources
 */
qx.Class.define("qxapp.io.rest.Resource", {
  extend: qx.io.rest.Resource,

  construct: function(description) {
    this.base(arguments, description);

    this.configureRequest(function(request, action, params, data) {
      let headers = [{
        key: "Accept",
        value: "application/json"
      }];

      if (this.__authentication !== null) {
        headers.concat(this.__authentication.getAuthHeaders());
      }

      headers.forEach(function(item, index, array) {
        request.setRequestHeader(item.key, item.value);
      });
    });
  },

  statics: {
    __authentication: null,

    setAutheticationHeader: function(usernameOrToken, password=null) {
      this.__authentication = new qx.io.request.authentication.Basic(usernameOrToken, password);
    }
  }

});
