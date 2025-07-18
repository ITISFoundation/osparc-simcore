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
      const functionData = this.__createFunctionData(templateData, name, description, defaultInputs, exposedInputs, exposedOutputs);
      const params = {
        data: functionData,
      };
      return osparc.data.Resources.fetch("functions", "create", params);
    },

    fetchFunctionsPaginated: function(params, options) {
      const isBackendReady = true;
      if (!isBackendReady) {
        return new Promise(resolve => {
          const response = this.__dummyResponse();
          response["params"] = params;
          resolve(response);
        });
      }
      return osparc.data.Resources.fetch("functions", "getPage", params, options)
        .then(response => {
          const functions = response["data"];
          functions.forEach(func => func["resourceType"] = "function");
          return response;
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    fetchFunction: function(functionId) {
      const isBackendReady = true;
      if (!isBackendReady) {
        return new Promise(resolve => {
          const response = this.__dummyResponse();
          resolve(response["data"][0]);
        });
      }
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
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    invalidateFunctions: function() {
      this.__functions = null;
      if (this.__functionsPromiseCached) {
        this.__functionsPromiseCached = null;
      }
    },

    __dummyResponse: function() {
      return {
        "_meta": {
          "limit": 10,
          "total": 1,
          "offset": 0,
          "count": 1
        },
        "data": [{
          "uuid": "0fab79c3-14b8-4625-a455-6dcbf74eb4f2",
          "functionClass": "PROJECT",
          "name": "Potential Function II",
          "description": "Function description",
          "inputSchema": {
            "schema_class": "application/schema+json",
            "schema_content": {
              "type": "object",
              "required": [
                "X"
              ],
              "properties": {
                "X": {
                  "type": "number"
                }
              }
            }
          },
          "outputSchema": {
            "schema_class": "application/schema+json",
            "schema_content": {
              "type": "object",
              "required": [
                "Out 1",
                "Out_2"
              ],
              "properties": {
                "Out 1": {
                  "type": "number"
                },
                "Out_2": {
                  "type": "number"
                }
              }
            }
          },
          "defaultInputs": {
            "X": 2,
            "Y": 1
          },
          "creationDate": "2025-05-16T12:22:31.063Z",
          "lastChangeDate": "2025-05-16T12:22:33.804Z",
          "accessRights": {
            "3": {
              "read": true,
              "write": true,
              "delete": true
            },
            "5": {
              "read": true,
              "write": false,
              "delete": false
            }
          },
          "thumbnail": "https://img.freepik.com/premium-vector/image-icon-design-vector-template_1309674-940.jpg",
          "workbench": {"50a50309-1dfc-5ad5-b2d9-c11697641f0b": {"key": "simcore/services/comp/itis/sleeper", "version": "2.1.6", "label": "sleeper", "inputs": {"input_2": 2, "input_3": false, "input_4": 0, "input_5": 0}, "inputsRequired": [], "inputNodes": ["2e348481-5042-5148-9196-590574747297", "69873032-770a-536b-adb6-0e6ea01720a4"]}, "2e348481-5042-5148-9196-590574747297": {"key": "simcore/services/frontend/parameter/number", "version": "1.0.0", "label": "X", "inputs": {}, "inputsRequired": [], "inputNodes": [], "outputs": {"out_1": 1}, "runHash": null}, "70e1de1a-a8b0-59e3-b19e-ea20f78765ce": {"key": "simcore/services/frontend/iterator-consumer/probe/number", "version": "1.0.0", "label": "Out 1", "inputs": {"in_1": 0}, "inputsRequired": [], "inputNodes": ["50a50309-1dfc-5ad5-b2d9-c11697641f0b"]}, "69873032-770a-536b-adb6-0e6ea01720a4": {"key": "simcore/services/frontend/parameter/number", "version": "1.0.0", "label": "Y", "inputs": {}, "inputsRequired": [], "inputNodes": [], "outputs": {"out_1": 1}, "runHash": null}, "24f856c3-408c-5ab4-ad01-e99630a355fe": {"key": "simcore/services/frontend/iterator-consumer/probe/number", "version": "1.0.0", "label": "Out_2", "inputs": {"in_1": 0}, "inputsRequired": [], "inputNodes": ["50a50309-1dfc-5ad5-b2d9-c11697641f0b"]}},
          "ui": {
            "workbench": {"24f856c3-408c-5ab4-ad01-e99630a355fe": {"position": {"x": 540, "y": 240}}, "2e348481-5042-5148-9196-590574747297": {"position": {"x": 120, "y": 140}}, "50a50309-1dfc-5ad5-b2d9-c11697641f0b": {"position": {"x": 300, "y": 180}}, "69873032-770a-536b-adb6-0e6ea01720a4": {"position": {"x": 120, "y": 240}}, "70e1de1a-a8b0-59e3-b19e-ea20f78765ce": {"position": {"x": 540, "y": 140}}},
            "mode": "pipeline",
          },
        }],
        "_links": {
          "next": null,
        },
      };
    },
  }
});
