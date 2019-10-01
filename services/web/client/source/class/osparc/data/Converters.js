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
 *   Collection of static methods for converting data coming from the webserver into suitable
 * data for the frontend.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dataStore = osparc.store.Data.getInstance();
 *   dataStore.addListenerOnce("nodeFiles", e => {
 *     const files = e.getData();
 *     const newChildren = osparc.data.Converters.fromDSMToVirtualTreeModel(files);
 *     this.__addTreeData(newChildren);
 *   }, this);
 *   dataStore.getNodeFiles(nodeId);
 * </pre>
 */

qx.Class.define("osparc.data.Converters", {
  type: "static",

  statics: {
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

    fromDSMToVirtualTreeModel: function(files) {
      let uuidToName = osparc.utils.UuidToName.getInstance();
      let children = [];
      for (let i=0; i<files.length; i++) {
        const file = files[i];
        let fileInTree = this.createDirEntry(
          file["location"],
          file["location_id"],
          ""
        );
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
            fileInTree.children.push(
              this.createDirEntry(
                prjLabel,
                file["location_id"],
                prjId,
                [this.createDirEntry(
                  nodeLabel,
                  file["location_id"],
                  prjId +"/"+ nodeId,
                  [this.createFileEntry(
                    fileName,
                    file["location_id"],
                    file["file_id"],
                    file["last_modified"],
                    file["file_size"])
                  ]
                )]
              )
            );
            this.__mergeFileTreeChildren(children, fileInTree);
          }
        } else if (file["location_id"] === 1 || file["location_id"] === "1") {
          // datcore files
          let parent = fileInTree;
          let splitted = file["file_uuid"].split("/");
          for (let j=0; j<splitted.length-1; j++) {
            const newItem = this.createDirEntry(
              splitted[j],
              file["location_id"],
              parent.path === "" ? splitted[j] : parent.path +"/"+ splitted[j]
            );
            parent.children.push(newItem);
            parent = newItem;
          }
          let fileInfo = this.createFileEntry(
            splitted[splitted.length-1],
            file["location_id"],
            file["file_id"],
            file["last_modified"],
            file["file_size"]);
          parent.children.push(fileInfo);
          this.__mergeFileTreeChildren(children, fileInTree);
        }
      }

      return children;
    },

    createDirEntry: function(label, location, path, children = []) {
      if (label === null || label === undefined || label === "") {
        label = "Unknown label";
      }
      return {
        label,
        location,
        path,
        children
      };
    },

    createFileEntry: function(label, location, fileId, lastModified, size) {
      if (label === undefined) {
        label = "Unknown label";
      }
      if (location === undefined) {
        location = "Unknown location";
      }
      if (fileId === undefined) {
        fileId = "Unknown fileId";
      }
      if (lastModified === undefined) {
        lastModified = (Math.floor(Math.random()*1000000)+1).toString();
      }
      if (size === undefined) {
        size = 0;
      }
      return {
        label,
        location,
        fileId,
        lastModified,
        size
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

    fromAPITreeToVirtualTreeModel: function(treeItems, showLeavesAsDirs, portKey) {
      let children = [];
      for (let i=0; i<treeItems.length; i++) {
        const treeItem = treeItems[i];
        let splitted = treeItem.label.split("/");
        let newItem = {
          label: splitted[0],
          open: false,
          portKey
        };
        if (splitted.length === 1) {
          // leaf already
          newItem.key = treeItem.key;
          if (showLeavesAsDirs) {
            newItem.children = [];
          }
        } else {
          // branch
          newItem.key = splitted[0];
          newItem.children = [];
          let parent = newItem;
          for (let j=1; j<splitted.length-1; j++) {
            let branch = {
              label: splitted[j],
              key: parent.key +"/"+ splitted[j],
              open: false,
              children: []
            };
            parent.children.push(branch);
            parent = branch;
          }
          let leaf = {
            label: splitted[splitted.length-1],
            open: false,
            key: parent.key +"/"+ splitted[splitted.length-1]
          };
          if (showLeavesAsDirs) {
            leaf.children = [];
          }
          parent.children.push(leaf);
        }
        this.__mergeAPITreeChildren(children, newItem);
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
    },

    fromTypeToIcon: function(type) {
      // Introduce further mappings here
      switch (type) {
        case "integer":
          return "@MaterialIcons/arrow_right_alt/15";
        case "string":
          return "@MaterialIcons/format_quote/15";
      }
      if (type.indexOf("data:") === 0) {
        return "@MaterialIcons/insert_drive_file/15";
      }
      return "@MaterialIcons/arrow_right_alt/15";
    }
  }
});
