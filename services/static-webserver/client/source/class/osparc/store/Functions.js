/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.store.Functions", {
  type: "static",

  statics: {
    __createFunctionData: function(templateData, name, description, defaultInputs = {}, exposedInputs = {}, exposedOutputs = {}) {
      const functionData = {
        "projectId": templateData["uuid"],
        "title": name,
        "description": description,
        "function_class": osparc.data.model.Function.FUNCTION_CLASS.PROJECT,
        "inputSchema": {
          "schema_class": "application/schema+json",
          "schema_content": {
            "type": "object",
            "properties": {},
            "required": []
          }
        },
        "outputSchema": {
          "schema_class": "application/schema+json",
          "schema_content": {
            "type": "object",
            "properties": {},
            "required": []
          }
        },
        "defaultInputs": {},
      };

      const parameters = osparc.study.Utils.extractFunctionableParameters(templateData["workbench"]);
      parameters.forEach(parameter => {
        const parameterKey = parameter["label"];
        if (exposedInputs[parameterKey]) {
          const parameterMetadata = osparc.store.Services.getMetadata(parameter["key"], parameter["version"]);
          if (parameterMetadata) {
            const type = osparc.service.Utils.getParameterType(parameterMetadata);
            functionData["inputSchema"]["schema_content"]["properties"][parameterKey] = {
              "type": type,
            };
            functionData["inputSchema"]["schema_content"]["required"].push(parameterKey);
          }
        }
        if (parameterKey in defaultInputs) {
          functionData["defaultInputs"][parameterKey] = defaultInputs[parameterKey];
        }
      });

      const probes = osparc.study.Utils.extractFunctionableProbes(templateData["workbench"]);
      probes.forEach(probe => {
        const probeLabel = probe["label"];
        if (exposedOutputs[probeLabel]) {
          const probeMetadata = osparc.store.Services.getMetadata(probe["key"], probe["version"]);
          if (probeMetadata) {
            const type = osparc.service.Utils.getProbeType(probeMetadata);
            functionData["outputSchema"]["schema_content"]["properties"][probeLabel] = {
              "type": type,
            };
            functionData["outputSchema"]["schema_content"]["required"].push(probeLabel);
          }
        }
      });

      return functionData;
    },

    registerFunction: function(templateData, name, description, defaultInputs, exposedInputs, exposedOutputs) {
      const functionData = this.__createFunctionData(templateData, name, description, defaultInputs, exposedInputs, exposedOutputs);
      const params = {
        data: functionData,
      };
      return osparc.data.Resources.fetch("functions", "create", params);
    },

    curateOrderBy: function(orderBy) {
      const curatedOrderBy = JSON.parse(orderBy);
      switch (curatedOrderBy.field) {
        case "last_change_date":
          curatedOrderBy.field = "modified_at";
          break;
        case "creation_date":
          curatedOrderBy.field = "created_at";
          break;
        case "name":
          // Backend does not currently support sorting by 'name'.
          // Fallback: sort by 'modified_at' instead.
          // TODO: Remove this workaround once backend supports sorting by 'name'.
          curatedOrderBy.field = "modified_at";
          break;
        default:
          // only those three are supported
          curatedOrderBy.field = "modified_at";
      }
      return JSON.stringify(curatedOrderBy);
    },

    fetchFunctionsPaginated: function(params, options) {
      if ("orderBy" in params["url"]) {
        params["url"]["orderBy"] = this.curateOrderBy(params["url"]["orderBy"]);
      }
      return osparc.data.Resources.fetch("functions", "getPage", params, options)
        .then(response => {
          const functions = response["data"];
          functions.forEach(func => func["resourceType"] = "function");
          return response;
        });
    },

    searchFunctionsPaginated: function(params, options) {
      if ("orderBy" in params["url"]) {
        params["url"]["orderBy"] = this.curateOrderBy(params["url"]["orderBy"]);
      }
      return osparc.data.Resources.fetch("functions", "getPageSearch", params, options)
        .then(response => {
          const functions = response["data"];
          functions.forEach(func => func["resourceType"] = "function");
          return response;
        });
    },

    fetchFunction: function(functionId) {
      const params = {
        url: {
          "functionId": functionId
        }
      };
      return osparc.data.Resources.fetch("functions", "getOne", params)
        .then(func => {
          func["resourceType"] = "function";
          return func;
        })
        .catch(error => {
          console.error("Error fetching function:", error);
          throw error; // Rethrow the error to propagate it to the caller
        });
    },

    patchFunction: function(functionId, functionChanges) {
      const params = {
        url: {
          functionId
        },
        data: functionChanges
      };
      return osparc.data.Resources.fetch("functions", "patch", params)
        .catch(error => {
          console.error("Error patching function:", error);
          throw error; // Rethrow the error to propagate it to the caller
        });
    },

    deleteFunction: function(functionId, force = false) {
      const params = {
        url: {
          functionId,
          force,
        }
      };
      return osparc.data.Resources.fetch("functions", "delete", params)
        .catch(error => {
          console.error("Error deleting function:", error);
          throw error; // Rethrow the error to propagate it to the caller
        });
    },

    __putCollaborator: function(functionData, gid, newPermissions) {
      const params = {
        url: {
          "functionId": functionData["uuid"],
          "gId": gid,
        },
        data: newPermissions
      };
      return osparc.data.Resources.fetch("functions", "putAccessRights", params)
    },

    addCollaborators: function(functionData, newCollaborators) {
      const promises = [];
      Object.keys(newCollaborators).forEach(gid => {
        promises.push(this.__putCollaborator(functionData, gid, newCollaborators[gid]));
      });
      return Promise.all(promises)
        .then(() => {
          Object.keys(newCollaborators).forEach(gid => {
            functionData["accessRights"][gid] = newCollaborators[gid];
          });
          functionData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    updateCollaborator: function(functionData, gid, newPermissions) {
      return this.__putCollaborator(functionData, gid, newPermissions)
        .then(() => {
          functionData["accessRights"][gid] = newPermissions;
          functionData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },

    removeCollaborator: function(functionData, gid) {
      const params = {
        url: {
          "functionId": functionData["uuid"],
          "gId": gid
        }
      };
      return osparc.data.Resources.fetch("functions", "deleteAccessRights", params)
        .then(() => {
          delete functionData["accessRights"][gid];
          functionData["lastChangeDate"] = new Date().toISOString();
        })
        .catch(err => {
          osparc.FlashMessenger.logError(err);
          throw err;
        });
    },
  }
});
