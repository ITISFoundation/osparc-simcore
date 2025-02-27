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

    createLoadingEntry: function() {
      return {
        label: "Loading...",
        location: null,
        path: null,
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12",
        type: "loading",
      };
    },

    createFolderEntry: function(displayPath, location, path) {
      if (displayPath === null || displayPath === undefined || displayPath === "") {
        displayPath = "Unknown label";
      }
      return {
        label: this.displayPathToLabel(displayPath, { last: true }),
        displayPath: decodeURIComponent(displayPath),
        location,
        path,
        itemId: path,
        children: [],
        type: "folder",
      };
    },

    createFileEntry: function(displayPath, location, path, datasetId, fileMetaData) {
      return {
        label: this.displayPathToLabel(displayPath, { last: true }),
        displayPath: decodeURIComponent(displayPath),
        location,
        path,
        itemId: path,
        datasetId,
        fileId: fileMetaData["file_uuid"],
        lastModified: fileMetaData["last_modified"],
        size: fileMetaData["file_size"],
        type: "file",
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
    },

    pathToDatasetId: function(path) {
      const splitted = path.split("/");
      if (splitted.length > 1) {
        // simcore: studyId + nodeId + fileId
        // datcore: datasetId + packageId
        return splitted[0];
      }
      return null;
    },

    displayPathToLabel: function(encodedDisplayPath, options) {
      const parts = encodedDisplayPath.split("/");
      const decodedParts = parts.map(decodeURIComponent);
      if (options.first) {
        return decodedParts[0];
      } else if (options.last) {
        return decodedParts[decodedParts.length-1];
      } else if ("pos" in options && options["pos"] < decodedParts.length) {
        return decodedParts[options["pos"]];
      }
      return decodedParts[0];
    },
  }
});
