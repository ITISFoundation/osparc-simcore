/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *  Collection of free function with fake data for testing
 *
 * TODO: Use faker https://scotch.io/tutorials/generate-fake-data-for-your-javascript-applications-using-faker
 */

qx.Class.define("osparc.dev.fake.Data", {
  type: "static",

  statics: {
    getFakeServices: function() {
      return [{
        key: "simcore/services/computational/itis/sleeper",
        version: "0.0.0",
        type: "computational",
        name: "sleeper service",
        description: "dummy sleepr service",
        authors: [
          {
            name: "Odei Maiz",
            email: "maiz@itis.ethz.ch"
          }
        ],
        contact: "maiz@itis.ethz.ch",
        inputs: {
          inNumber: {
            displayOrder: 0,
            label: "In",
            description: "Chosen Number",
            type: "number",
            defaultValue: 42
          }
        },
        outputs: {
          outNumber: {
            displayOrder: 0,
            label: "Out",
            description: "Chosen Number",
            type: "number"
          }
        }
      }, {
        key: "simcore/services/computational/itis/tutti",
        version: "0.0.0",
        type: "computational",
        name: "a little test node",
        description: "just the bare minimum",
        authors: [
          {
            name: "Tobias Oetiker",
            email: "oetiker@itis.ethz.ch"
          }
        ],
        contact: "oetiker@itis.ethz.ch",
        inputs: {
          inNumber: {
            displayOrder: 0,
            label: "Number Test",
            description: "Test Input for Number",
            type: "number",
            defaultValue: 5.3
          },
          inInt: {
            displayOrder: 1,
            label: "Integer Test",
            description: "Test Input for Integer",
            type: "integer",
            defaultValue: 2
          },
          inBool: {
            displayOrder: 2,
            label: "Boolean Test",
            type: "boolean",
            description: "Test Input for Boolean",
            defaultValue: true
          },
          inStr: {
            displayOrder: 3,
            type: "string",
            label: "String Test",
            description: "Test Input for String",
            defaultValue: "Gugus"
          },
          inArea: {
            displayOrder: 4,
            type: "string",
            label: "Widget TextArea Test",
            description: "Test Input for String",
            defaultValue: "Gugus\nDu\nDa",
            widget: {
              type: "TextArea",
              minHeight: 50
            }
          },
          inSb: {
            displayOrder: 5,
            label: "Widget SelectBox Test",
            description: "Test Input for SelectBox",
            defaultValue: "dog",
            type: "string",
            widget: {
              /*
              type: "SelectBox",
              structure: [
                {
                  key: "dog",
                  label: "A Dog"
                },
                {
                  key: "cat",
                  label: "A Cat"
                }
              ]
              */
              type: "TextArea",
              minHeight: 50
            }
          },
          inFile: {
            displayOrder: 6,
            label: "File",
            description: "Test Input File",
            type: "data:*/*"
          },
          inImage: {
            displayOrder: 7,
            label: "Image",
            description: "Test Input Image",
            type: "data:[image/jpeg,image/png]"
          }
        },
        outputs: {
          outNumber: {
            label: "Number Test",
            description: "Test Output for Number",
            displayOrder: 0,
            type: "number"
          },
          outInteger: {
            label: "Integer Test",
            description: "Test Output for Integer",
            displayOrder: 1,
            type: "integer"
          },
          outBool: {
            label: "Boolean Test",
            description: "Test Output for Boolean",
            displayOrder: 2,
            type: "boolean"
          },
          outPng: {
            label: "Png Test",
            description: "Test Output for PNG Image",
            displayOrder: 3,
            type: "data:image/png"
          }
        }
      }];
    },

    getItemList: function(nodeKey, portKey) {
      switch (portKey) {
        case "defaultNeuromanModels":
          return osparc.dev.fake.neuroman.Data.getItemList(portKey);
        case "modeler":
          return osparc.dev.fake.modeler.Data.getItemList();
        case "materialDB":
          return osparc.dev.fake.materialDB.Data.getItemList();
        case "defaultLFMaterials":
        case "defaultLFBoundaries":
        case "defaultLFSensors":
        case "sensorSettingAPI":
          return osparc.dev.fake.lf.Data.getItemList(portKey);
        case "defaultNeurons":
        case "defaultNeuronSources":
        case "defaultNeuronPointProcesses":
        case "defaultNeuronNetworkConnection":
        case "defaultNeuronSensors":
        case "neuronsSetting":
          return osparc.dev.fake.neuron.Data.getItemList(portKey);
        case "defaultStimulationSelectivity":
          return osparc.dev.fake.stimulationSelectivity.Data.getItemList();
      }
      return [];
    },

    getItem: function(nodeInstanceUUID, portKey, itemUuid) {
      switch (portKey) {
        case "materialDB":
          return osparc.dev.fake.materialDB.Data.getItem(itemUuid);
        case "defaultLFMaterials":
        case "defaultLFBoundaries":
        case "defaultLFSensors":
          return osparc.dev.fake.lf.Data.getItem(portKey, itemUuid);
        case "defaultNeurons":
        case "defaultNeuronSources":
        case "defaultNeuronPointProcesses":
        case "defaultNeuronNetworkConnection":
        case "defaultNeuronSensors":
          return osparc.dev.fake.neuron.Data.getItem(portKey, itemUuid);
      }
      return {};
    }
  } // statics

});
