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
    __functions: null,
    __functionsPromiseCached: null,

    __createFunctionData: function(templateData, name, description, defaultInputs = {}, exposedInputs = {}, exposedOutputs = {}) {
      const functionData = {
        "projectId": templateData["uuid"],
        "title": name,
        "description": description,
        "function_class": "PROJECT",
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
      const functionData = this.self().__createFunctionData(templateData, name, description, defaultInputs, exposedInputs, exposedOutputs);
      const params = {
        data: functionData,
      };
      return osparc.data.Resources.fetch("functions", "create", params);
    },

    fetchFunctionsPaginated: function(params, options) {
      return osparc.data.Resources.fetch("functions", "getPage", params, options)
        .then(response => {
          const functions = response["data"];
          functions.forEach(func => func["resourceType"] = "function");
          return response;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchFunction: function(functionId) {
      return osparc.store.Study.getInstance().getOne(functionId)
        .catch(err => console.error(err));
    },

    getFunction: function(functionId) {
      if (this.__functions) {
        const func = this.__functions.find(t => t["functionId"] === functionId);
        if (func) {
          return new osparc.data.model.Function(func);
        }
      }
      return null;
    },

    invalidateFunctions: function() {
      this.__functions = null;
      if (this.__functionsPromiseCached) {
        this.__functionsPromiseCached = null;
      }
    },
  }
});
