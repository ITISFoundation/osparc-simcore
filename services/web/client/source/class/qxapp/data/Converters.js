
qx.Class.define("qxapp.data.Converters", {
  type: "static",

  statics: {
    registryToMetaData: function(data) {
      let metaData = {};
      [
        "key",
        "version",
        "type",
        "name",
        "description",
        "authors",
        "contact",
        "inputs",
        "outputs"
      ].forEach(field => {
        metaData[field] = null;
        if (Object.prototype.hasOwnProperty.call(data, field)) {
          metaData[field] = data[field];
        }
      });
      return metaData;
    },

    mergeChildren: function(one, two) {
      let newDir = true;
      for (let i=0; i<one.length; i++) {
        if (one[i].label === two.label) {
          newDir = false;
          if ("children" in two) {
            this.mergeChildren(one[i].children, two.children[0]);
          }
        }
      }
      if (one.length === 0 || "fileId" in two || newDir) {
        one.push(two);
      }
    },

    fromDSMToVirtualTreeModel: function(files) {
      let children = [];
      for (let i=0; i<files.length; i++) {
        const file = files[i];
        let fileInTree = {
          label: file["location"],
          children: [{
            label: file["bucket_name"],
            children: []
          }]
        };
        let bucketChildren = fileInTree.children[0].children;
        let splitted = file["object_name"].split("/");
        if (file["location"] === "simcore.s3") {
          // simcore files
          if (splitted.length === 2) {
            // user file
            bucketChildren.push({
              label: file["user_name"],
              children: [{
                label: file["file_name"],
                fileId: file["file_uuid"]
              }]
            });
            this.mergeChildren(children, fileInTree);
          } else if (splitted.length === 3) {
            // node file
            bucketChildren.push({
              label: file["project_name"],
              children: [{
                label: file["node_name"],
                children: [{
                  label: file["file_name"],
                  fileId: file["file_uuid"]
                }]
              }]
            });
            this.mergeChildren(children, fileInTree);
          }
        } else {
          // other files
          bucketChildren.push({
            label: file["file_name"],
            fileId: file["file_uuid"]
          });
          this.mergeChildren(children, fileInTree);
        }
      }

      return children;
    }
  }
});
