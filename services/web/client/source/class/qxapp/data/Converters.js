/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

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

    __mergeFileTreeChildren: function(one, two) {
      let newDir = true;
      for (let i=0; i<one.length; i++) {
        if (one[i].path === two.path) {
          newDir = false;
          if ("children" in two) {
            this.__mergeFileTreeChildren(one[i].children, two.children[0]);
          }
        }
      }
      if (one.length === 0 || "fileId" in two || newDir) {
        one.push(two);
      }
    },

    __isLocationValid: function(locID) {
      if (locID === 0 || locID === "0" ||
        locID === 1 || locID === "1") {
        return true;
      }
      return false;
    },

    fromDSMToVirtualTreeModel: function(files) {
      let uuidToName = qxapp.utils.UuidToName.getInstance();
      let children = [];
      for (let i=0; i<files.length; i++) {
        const file = files[i];
        if (this.__isLocationValid(file["location_id"])) {
          let fileInTree = {
            label: file["location"],
            location: file["location_id"],
            path: "",
            children: []
          };
          if (file["location_id"] === 0 || file["location_id"] === "0") {
            // simcore files
            let splitted = file["file_uuid"].split("/");
            if (splitted.length === 3) {
              const prjId = splitted[0];
              const nodeId = splitted[1];
              const fileId = splitted[2];
              let prjLabel = file["project_name"] === "" ? uuidToName.convertToName(prjId) : file["project_name"];
              let nodeLabel = file["node_name"] === "" ? uuidToName.convertToName(nodeId) : file["node_name"];
              let fileName = file["file_name"] === "" ? fileId : file["file_name"];
              // node file
              fileInTree.children.push({
                label: prjLabel,
                location: file["location_id"],
                path: prjId,
                children: [{
                  label: nodeLabel,
                  location: file["location_id"],
                  path: prjId +"/"+ nodeId,
                  children: [this.__createFileEntry(
                    fileName,
                    file["location_id"],
                    file["file_uuid"],
                    file["size"])
                  ]
                }]
              });
              this.__mergeFileTreeChildren(children, fileInTree);
            }
          } else if (file["location_id"] === 1 || file["location_id"] === "1") {
            // datcore files
            let parent = fileInTree;
            let splitted = file["file_uuid"].split("/");
            for (let j=0; j<splitted.length-1; j++) {
              const newItem = {
                label: splitted[j],
                location: file["location_id"],
                path: parent.path === "" ? splitted[j] : parent.path +"/"+ splitted[j],
                children: []
              };
              parent.children.push(newItem);
              parent = newItem;
            }
            let fileInfo = this.__createFileEntry(
              splitted[splitted.length-1],
              file["location_id"],
              file["file_uuid"],
              file["size"]);
            parent.children.push(fileInfo);
            this.__mergeFileTreeChildren(children, fileInTree);
          }
        }
      }

      return children;
    },

    __createFileEntry: function(label, location, fileId, size) {
      if (label === undefined) {
        label = "Unknown label";
      }
      if (location === undefined) {
        location = "Unknown location";
      }
      if (fileId === undefined) {
        fileId = "Unknown fileId";
      }
      if (size === undefined) {
        size = (Math.floor(Math.random()*1000000)+1).toString();
      }
      return {
        label: label,
        location: location,
        fileId: fileId,
        size: size
      };
    },

    __mergeAPITreeChildren: function(one, two) {
      let newDir = true;
      for (let i=0; i<one.length; i++) {
        if (one[i].key === two.key) {
          newDir = false;
          if ("children" in two) {
            this.__mergeAPITreeChildren(one[i].children, two.children[0]);
          }
        }
      }
      // if (one.length === 0 || "fileId" in two || newDir) {
      if (one.length === 0 || newDir) {
        one.push(two);
      }
    },

    fromAPITreeToVirtualTreeModel: function(treeItems, showLeavesAsDirs = false) {
      let children = [];
      for (let i=0; i<treeItems.length; i++) {
        const treeItem = treeItems[i];
        let splitted = treeItem["label"].split("/");
        let newItem = {
          "label": splitted[0]
        };
        if (splitted.length === 1) {
          // leaf already
          newItem["key"] = treeItem["key"];
          if (showLeavesAsDirs) {
            newItem["children"] = [];
          }
        } else {
          // branch
          newItem["key"] = splitted[0];
          newItem["children"] = [];
          let parent = newItem;
          for (let j=1; j<splitted.length-1; j++) {
            let branch = {
              label: splitted[j],
              key: parent.key +"/"+ splitted[j],
              children: []
            };
            parent.children.push(branch);
            parent = branch;
          }
          let leaf = {
            label: splitted[splitted.length-1],
            key: parent.key +"/"+ splitted[splitted.length-1]
          };
          if (showLeavesAsDirs) {
            leaf["children"] = [];
          }
          parent.children.push(leaf);
        }
        this.__mergeAPITreeChildren(children, newItem);
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
        if (listItem.thumbnail) {
          item["thumbnail"] = listItem["thumbnail"];
        }
        list.push(item);
      }
      return list;
    }
  }
});
