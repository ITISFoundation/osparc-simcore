
qx.Class.define("qxapp.data.Converters", {
  type: "static",

  statics: {
    registryToMetaData: function(data) {
      let metaData = {};
      [
        "key",
        "name",
        "version",
        "type",
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
      return metaData;
    }
  }
});
