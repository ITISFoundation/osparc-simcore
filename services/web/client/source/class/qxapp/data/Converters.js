
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
        if (file["location_id"] === 0 || file["location_id"] === "0") {
          // simcore files
          let splitted = file["file_uuid"].split("/");
          if (splitted.length === 3) {
            const prjId = splitted[0];
            const nodejId = splitted[1];
            const fileId = splitted[2];
            // node file
            fileInTree.children.push({
              label: file["project_name"] ? file["project_name"] : prjId,
              path: fileInTree.path +"/"+ file["project_name"],
              children: [{
                label: file["node_name"] ? file["node_name"] : nodejId,
                path: fileInTree.path +"/"+ file["project_name"] +"/"+ file["node_name"],
                children: [{
                  label: file["file_name"] ? file["file_name"] : fileId,
                  fileId: file["file_uuid"],
                  location: file["location_id"]
                }]
              }]
            });
            this.mergeChildren(children, fileInTree);
          }
        } else if (file["location_id"] === 1 || file["location_id"] === "1") {
          // datcore files
          let parent = fileInTree;
          let splitted = file["file_uuid"].split("/");
          for (let j=0; j<splitted.length-1; j++) {
            const newItem = {
              label: splitted[j],
              path: parent.path +"/"+ splitted[j],
              children: []
            };
            parent.children.push(newItem);
            parent = newItem;
          }
          let fileInfo = {
            label: splitted[splitted.length-1],
            fileId: file["file_uuid"],
            location: file["location_id"]
          };
          parent.children.push(fileInfo);
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
