
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
          path: file["location"],
          children: []
        };
        fileInTree.children.push({
          label: file["bucket_name"],
          path: file["location"] + "/" + file["bucket_name"],
          children: []
        });
        let bucketItem = fileInTree.children[0];
        let splitted = file["object_name"].split("/");
        if (file["location"] === "simcore.s3") {
          // simcore files
          if (splitted.length === 2) {
            // user file
            bucketItem.children.push({
              label: file["user_name"],
              path: bucketItem.path +"/"+ file["user_name"],
              children: [{
                label: file["file_name"],
                fileId: file["file_uuid"]
              }]
            });
            this.mergeChildren(children, fileInTree);
          } else if (splitted.length === 3) {
            // node file
            bucketItem.children.push({
              label: file["project_name"],
              path: bucketItem.path +"/"+ file["project_name"],
              children: [{
                label: file["node_name"],
                path: bucketItem.path +"/"+ file["project_name"] +"/"+ file["node_name"],
                children: [{
                  label: file["file_name"],
                  fileId: file["file_uuid"]
                }]
              }]
            });
            this.mergeChildren(children, fileInTree);
          }
        } else if (file["location"] === "simcore.sandbox") {
          for (let j=0; j<splitted.length-1; j++) {
            const newDir = {
              label: splitted[j],
              path: bucketItem.path +"/"+ splitted[j],
              children: []
            };
            bucketItem.children.push(newDir);
            bucketItem = bucketItem.children[0];
          }
          let fileInfo = {
            label: splitted[splitted.length-1],
            fileId: file["file_uuid"]
          };
          bucketItem.children.push(fileInfo);
          this.mergeChildren(children, fileInTree);
        } else {
          // other files
          bucketItem.children.push({
            label: file["file_name"],
            fileId: file["file_uuid"]
          });
          this.mergeChildren(children, fileInTree);
        }
      }

      return children;
    },

    fromAPIListToVirtualTreeModel: function(listItems, showLeavesAsDirs = false) {
      let children = [];
      for (let i=0; i<listItems.length; i++) {
        const listItem = listItems[i];
        let item = {
          key: listItem["key"],
          label: listItem["label"]
        };
        if (showLeavesAsDirs) {
          item["children"] = [];
        }
        children.push(item);
      }
      return children;
    },

    fromAPIListToVirtualListModel: function(listItems) {
      let list = [];
      for (let i=0; i<listItems.length; i++) {
        const listItem = listItems[i];
        let item = {
          key: listItem["key"],
          label: listItem["label"]
        };
        if (Object.prototype.hasOwnProperty.call(listItem, "thumbnail")) {
          item["thumbnail"] = listItem["thumbnail"];
        }
        list.push(item);
      }
      return list;
    }
  }
});
