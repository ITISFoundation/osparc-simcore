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
 *  data for the frontend.
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

    sortFiles: function(children) {
      if (children && children.length) {
        children.sort((a, b) => {
          if (a["label"] > b["label"]) {
            return 1;
          }
          if (a["label"] < b["label"]) {
            return -1;
          }
          return 0;
        });
        children.forEach(child => {
          if ("children" in child) {
            this.sortFiles(child["children"]);
          }
        });
      }
    },

    sortModelByLabel: function(model) {
      model.getChildren().sort((a, b) => {
        if (a.getLabel() > b.getLabel()) {
          return 1;
        }
        if (a.getLabel() < b.getLabel()) {
          return -1;
        }
        return 0;
      });
    },

    fromDSMToVirtualTreeModel: function(datasetId, files) {
      let children = [];
      for (let i=0; i<files.length; i++) {
        const file = files[i];
        let fileInTree = this.createDirEntry(
          file["location"],
          file["location_id"],
          ""
        );
        const isSimcore = file["location_id"] === 0 || file["location_id"] === "0";

        const splitted = file["file_uuid"].split("/");
        if (isSimcore && splitted.length < 3) {
          continue;
        }

        // create directories
        let parent = fileInTree;
        for (let j=0; j<splitted.length-1; j++) {
          let label = "Unknown";
          if (isSimcore && j===0) {
            label = file["project_name"];
          } else if (isSimcore && j===1) {
            label = file["node_name"];
          } else {
            label = splitted[j];
          }
          const newItem = this.createDirEntry(
            label,
            file["location_id"],
            parent.path === "" ? splitted[j] : parent.path +"/"+ splitted[j]
          );
          parent.children.push(newItem);
          parent = newItem;
        }

        // create file
        const fileInfo = this.__createFileEntry(
          splitted[splitted.length-1],
          file["location_id"],
          datasetId,
          file["file_id"],
          file["last_modified"],
          file["file_size"]
        );
        parent.children.push(fileInfo);
        this.__mergeFileTreeChildren(children, fileInTree);
      }

      this.sortFiles(children);
      return children;
    },

    createDirEntry: function(displayPath, location, path) {
      if (displayPath === null || displayPath === undefined || displayPath === "") {
        displayPath = "Unknown label";
      }
      return {
        label: displayPath.split("/").slice(-1).pop(), // take last part of the display name
        displayPath,
        location,
        path,
        itemId: path,
        children: [],
      };
    },

    createFileEntry: function(displayPath, location, path, fileMetaData) {
      if (displayPath === undefined) {
        displayPath = "Unknown label";
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
        label: displayPath.split("/").slice(-1).pop(), // take last part of the display name
        displayPath,
        location,
        datasetId,
        fileId: path,
        itemId: path,
        lastModified,
        size
      };
    },

    __createFileEntry: function(label, location, datasetId, fileId, lastModified, size) {
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
        datasetId,
        fileId,
        itemId: fileId,
        lastModified,
        size
      };
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
