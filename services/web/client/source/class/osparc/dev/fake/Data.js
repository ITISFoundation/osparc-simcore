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
