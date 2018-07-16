/**
 * TODO: sync with definition of server API
 * TODO: these Resource classes have many things in common!?
*/
qx.Class.define("qxapp.io.rest.User", {
  extend: qxapp.io.rest.AbstractResource,

  construct: function() {
    this.base(arguments, {
      // Retrieve user current auth user
      get: {
        method: "GET",
        url: this.formatUrl("/users")
      },

      // Create new user
      post: {
        method: "POST",
        url: this.formatUrl("/users")
      }
    });
  }

});
