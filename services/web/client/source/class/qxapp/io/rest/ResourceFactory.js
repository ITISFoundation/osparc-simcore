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
      var project = new qx.io.rest.Resource({
        // Retrieve project
        get: {
          method: "GET",
          url: basePath+"/projects/{project_id}"
        },

        // Update project
        put: {
          method: "POST",
          url: basePath+"/projects/{project_id}"
        },

        // Delete project
        del: {
          method: "DELETE",
          url: basePath+"/projects/{project_id}"
        }
      });

      // Plural resource
      var projects = new qx.io.rest.Resource({
        // Retrieve list of projects
        get: {
          method: "GET",
          url: basePath+"/projects?type=user"
        },

        // Create project
        post: {
          method: "POST",
          url: basePath+"/projects"
        }
      });

      var templates = new qx.io.rest.Resource({
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
