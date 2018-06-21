
qx.Class.define("qxapp.data.Converters", {
  type: "static",

  statics: {
    registryToMetadata: function(data) {
      let metadata = {};
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
        metadata[field] = null;
        if (Object.prototype.hasOwnProperty.call(data, field)) {
          metadata[field] = data[field];
        }
      });
      return metadata;
    }
  }
});
