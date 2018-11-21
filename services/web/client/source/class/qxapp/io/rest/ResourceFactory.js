qx.Class.define("qxapp.io.rest.ResourceFactory", {
  extend: qx.core.Object,
  type : "singleton",

  statics: {
    API: "/v0"
  },

  members: {
    createProjectResources: function() {
      // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
      // SEE: api/specs/webserver/v0/openapi-projects.yaml
      const basePath = qxapp.io.rest.ResourceFactory.API;

      // Singular resource
      var project = new qxapp.io.rest.Resource({
        // Retrieve project
        get: {
          method: "GET",
          url: basePath+"/projects/{project_id}"
        },

        // Update project
        put: {
          method: "PUT",
          url: basePath+"/projects/{project_id}"
        },

        // Delete project
        del: {
          method: "DELETE",
          url: basePath+"/projects/{project_id}"
        }
      });

      // Plural resource
      var projects = new qxapp.io.rest.Resource({
        // Retrieve list of projects
        get: {
          method: "GET",
          url: basePath+"/projects?type=user"
        },

        // Create project
        // NOTE: When calling ".post(null, payload)" the first argument needs to be filled in
        // so that the second argument contains the payload
        post: {
          method: "POST",
          url: basePath+"/projects"
        }
      });

      var templates = new qxapp.io.rest.Resource({
        // Retrieve list of projects
        get: {
          method: "GET",
          url: basePath+"/projects?type=template"
        }
      });


      return {
        "project": project,
        "projects": projects,
        "templates": templates
      };
    }

  } // members
});
