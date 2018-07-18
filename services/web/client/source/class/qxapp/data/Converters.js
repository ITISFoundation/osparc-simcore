
qx.Class.define("qxapp.data.Converters", {
  type: "static",

  statics: {
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
