/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.io.rest.ResourceFactory", {
  extend: qx.core.Object,
  type : "singleton",

  statics: {
    API: "/v0"
  },

  members: {
    __config: null,

    requestConfig: function() {
      if (this.__config === null) {
        // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
        // SEE: api/specs/webserver/v0/openapi.yaml
        const basePath = osparc.io.rest.ResourceFactory.API;
        const configCheck = new osparc.io.rest.Resource({
          get: {
            method: "GET",
            url: basePath+"/config"
          }
        });
        configCheck.addListener("getSuccess", e => {
          this.__config = e.getRequest().getResponse().data;
        }, this);
        configCheck.addListener("getError", e => {
          console.error(e);
          this.__config === null;
        }, this);
        configCheck.get();
        this.__config === false;
      }
    },

    registerWithInvitation: function() {
      if (this.__config === null) {
        this.requestConfig();
        return null;
      }
      if (!("invitation_required" in this.__config)) {
        this.requestConfig();
        return null;
      }
      return this.__config["invitation_required"];
    },

    createHealthCheck: function() {
      // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
      // SEE: api/specs/webserver/v0/openapi-user.yaml
      const basePath = osparc.io.rest.ResourceFactory.API;

      // Singular resource
      let healthCheck = new osparc.io.rest.Resource({
        // Get health check
        get: {
          method: "GET",
          url: basePath+"/"
        }
      });

      return {
        "healthCheck": healthCheck
      };
    },

    createStudyResources: function() {
      // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
      // SEE: api/specs/webserver/v0/openapi-projects.yaml
      const basePath = osparc.io.rest.ResourceFactory.API;

      // Singular resource
      const study = new osparc.io.rest.Resource({
        // Retrieve study
        get: {
          method: "GET",
          url: basePath+"/projects/{project_id}"
        },

        // Update study
        put: {
          method: "PUT",
          url: basePath+"/projects/{project_id}"
        },

        // Delete study
        del: {
          method: "DELETE",
          url: basePath+"/projects/{project_id}"
        }
      });

      // Plural resource
      const studies = new osparc.io.rest.Resource({
        // Retrieve list of studies
        get: {
          method: "GET",
          url: basePath+"/projects?type=user"
        },

        // Create study
        // NOTE: When calling ".post(null, payload)" the first argument needs to be filled in
        // so that the second argument contains the payload
        post: {
          method: "POST",
          url: basePath+"/projects"
        },

        postFromTemplate: {
          method: "POST",
          url: basePath+"/projects?from_template={template_id}"
        },

        postSaveAsTemplate: {
          method: "POST",
          url: basePath+"/projects?as_template={study_id}"
        }
      });

      var templates = new osparc.io.rest.Resource({
        // Retrieve list of studies
        get: {
          method: "GET",
          url: basePath+"/projects?type=template"
        }
      });


      return {
        "project": study,
        "projects": studies,
        "templates": templates
      };
    },

    createUserResources: function() {
      // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
      // SEE: api/specs/webserver/v0/openapi-user.yaml
      const basePath = osparc.io.rest.ResourceFactory.API;

      // Singular resource
      let profile = new osparc.io.rest.Resource({
        // Get token
        get: {
          method: "GET",
          url: basePath+"/me"
        }
      });

      return {
        "profile": profile
      };
    },

    createTokenResources: function() {
      // SEE: https://www.qooxdoo.org/current/pages/communication/rest.html
      // SEE: api/specs/webserver/v0/openapi-user.yaml
      const basePath = osparc.io.rest.ResourceFactory.API;

      // Singular resource
      let token = new osparc.io.rest.Resource({
        // Get token
        get: {
          method: "GET",
          url: basePath+"/me/tokens/{service}"
        },

        // Update token
        put: {
          method: "PUT",
          url: basePath+"/me/tokens/{service}"
        },

        // Delete token
        del: {
          method: "DELETE",
          url: basePath+"/me/tokens/{service}"
        }
      });

      // Plural resource
      var tokens = new osparc.io.rest.Resource({
        // Retrieve tokens
        get: {
          method: "GET",
          url: basePath+"/me/tokens"
        },

        // Create token
        post: {
          method: "POST",
          url: basePath+"/me/tokens"
        }
      });

      return {
        "token": token,
        "tokens": tokens
      };
    }

  } // members
});
