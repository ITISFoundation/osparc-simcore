/**
 * TODO: sync with definition of server API
*/
qx.Class.define("qxapp.io.rest.Project", {
  extend: qxapp.io.rest.AbstractResource,

  construct: function() {
    this.base(arguments, {
      // Retrieve projects from current auth user
      get: {
        method: "GET",
        url: this.formatUrl("/projects")
      },

      // Create new project for current user
      post: {
        method: "POST",
        url: this.formatUrl("/projects")
      }
    });
  }

});
