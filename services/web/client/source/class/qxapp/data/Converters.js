
qx.Class.define("qxapp.data.Converters", {
  type: "static",

  statics: {
    metaDataToNodeData: function(metaData) {
      let nodeData = {
        key: metaData.key,
        version: metaData.version,
        inputs: {},
        outputs: {}
      };
      for (let inputKey in metaData.inputs) {
        nodeData.inputs[inputKey] = metaData.inputs[inputKey].defaultValue;
      }
      for (let outputKey in metaData.outputs) {
        nodeData.outputs[outputKey] = null;
      }
      return nodeData;
    },

    registryToMetaData: function(data) {
      let metaData = {};
      [
        "key",
        "name",
        "tag",
        "description",
        "authors",
        "contact",
        "inputs",
        "outputs",
        "settings"
      ].forEach(field => {
        metaData[field] = null;
        if (Object.prototype.hasOwnProperty.call(data, field)) {
          metaData[field] = data[field];
        }
      });
      // for dynamic services
      if (data.viewer) {
        metaData["viewer"] = data["viewer"];
      }
      return metaData;
    }
  }
});
