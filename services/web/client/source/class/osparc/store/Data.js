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
 * Singleton class that is used as entrypoint to the webserver.
 *
 * All data transfer communication goes through the osparc.store.Store.
 */

qx.Class.define("osparc.store.Data", {
  extend: qx.core.Object,

  type : "singleton",

  construct: function() {
    this.resetCache();
  },

  events: {
    "locations": "qx.event.type.Data",
    "datasetsInLocation": "qx.event.type.Data",
    "filesInDataset": "qx.event.type.Data",
    "filesInNode": "qx.event.type.Data",
    "fileCopied": "qx.event.type.Data",
    "deleteFile": "qx.event.type.Data",
    "presignedLink": "qx.event.type.Data"
  },

  members: {
    __locationsCached: null,
    __datasetsByLocationCached: null,
    __filesByLocationAndDatasetCached: null,

    resetCache: function() {
      this.__locationsCached = [];
      this.__datasetsByLocationCached = {};
      this.__filesByLocationAndDatasetCached = {};

      osparc.store.Store.getInstance().reset("storageLocations");
    },

    getLocationsCached: function() {
      const cache = this.__locationsCached;
      if (cache.length) {
        return cache;
      }
      return null;
    },

    getLocations: function() {
      const cachedData = this.getLocationsCached();
      if (cachedData) {
        this.fireDataEvent("locations", cachedData);
        return;
      }
      // Get available storage locations
      osparc.data.Resources.get("storageLocations")
        .then(locations => {
          // Add it to cache
          this.__locationsCached = locations;
          this.fireDataEvent("locations", locations);
        })
        .catch(err => {
          this.fireDataEvent("locations", []);
          console.error(err);
        });
    },

    getDatasetsByLocationCached: function(locationId) {
      const cache = this.__datasetsByLocationCached;
      if (locationId in cache && cache[locationId].length) {
        const data = {
          location: locationId,
          datasets: cache[locationId]
        };
        return data;
      }
      return null;
    },

    getDatasetsByLocation: function(locationId) {
      // Get list of datasets
      if (locationId === 1 && !osparc.data.Permissions.getInstance().canDo("storage.datcore.read")) {
        return;
      }

      const cachedData = this.getDatasetsByLocationCached(locationId);
      if (cachedData) {
        this.fireDataEvent("datasetsInLocation", cachedData);
        return;
      }

      const params = {
        url: {
          locationId
        }
      };
      osparc.data.Resources.fetch("storageDatasets", "getByLocation", params)
        .then(datasets => {
          const data = {
            location: locationId,
            datasets: []
          };
          if (datasets && datasets.length>0) {
            data.datasets = datasets;
          }
          // Add it to cache
          this.__datasetsByLocationCached[locationId] = data.datasets;
          this.fireDataEvent("datasetsInLocation", data);
        })
        .catch(err => {
          const data = {
            location: locationId,
            datasets: []
          };
          this.fireDataEvent("datasetsInLocation", data);
          console.error(err);
        });
    },

    getFilesByLocationAndDatasetCached: function(locationId, datasetId) {
      const cache = this.__filesByLocationAndDatasetCached;
      if (locationId in cache && datasetId in cache[locationId]) {
        const data = {
          location: locationId,
          dataset: datasetId,
          files: cache[locationId][datasetId]
        };
        return data;
      }
      return null;
    },

    getFilesByLocationAndDataset: function(locationId, datasetId) {
      // Get list of file meta data
      if (locationId === 1 && !osparc.data.Permissions.getInstance().canDo("storage.datcore.read")) {
        return;
      }

      const cachedData = this.getFilesByLocationAndDatasetCached(locationId, datasetId);
      if (cachedData) {
        this.fireDataEvent("filesInDataset", cachedData);
        return;
      }

      const params = {
        url: {
          locationId,
          datasetId
        }
      };
      osparc.data.Resources.fetch("storageFiles", "getByLocationAndDataset", params)
        .then(files => {
          const data = {
            location: locationId,
            dataset: datasetId,
            files: files && files.length>0 ? files : []
          };
          // Add it to cache
          if (!(locationId in this.__filesByLocationAndDatasetCached)) {
            this.__filesByLocationAndDatasetCached[locationId] = {};
          }
          this.__filesByLocationAndDatasetCached[locationId][datasetId] = data.files;
          this.fireDataEvent("filesInDataset", data);
        })
        .catch(err => {
          const data = {
            location: locationId,
            dataset: datasetId,
            files: []
          };
          this.fireDataEvent("filesInDataset", data);
          console.error(err);
        });
    },

    getNodeFiles: function(nodeId) {
      const params = {
        url: {
          nodeId: encodeURIComponent(nodeId)
        }
      };
      osparc.data.Resources.fetch("storageFiles", "getByNode", params)
        .then(files => {
          console.log("Node Files", files);
          if (files && files.length>0) {
            this.fireDataEvent("filesInNode", files);
          }
          this.fireDataEvent("filesInNode", []);
        })
        .catch(err => {
          this.fireDataEvent("filesInNode", []);
          console.error(err);
        });
    },

    getPresignedLink: function(download = true, locationId, fileUuid) {
      if (download && !osparc.data.Permissions.getInstance().canDo("study.node.data.pull", true)) {
        return;
      }
      if (!download && !osparc.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return;
      }

      // GET: Returns download link for requested file
      // POST: Returns upload link or performs copy operation to datcore
      const params = {
        url: {
          locationId,
          fileUuid: encodeURIComponent(fileUuid)
        }
      };
      osparc.data.Resources.fetch("storageLink", download ? "getOne" : "put", params)
        .then(data => {
          const presignedLinkData = {
            presignedLink: data,
            locationId: locationId,
            fileUuid: fileUuid
          };
          console.log("presignedLink", presignedLinkData);
          this.fireDataEvent("presignedLink", presignedLinkData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    copyFile: function(fromLoc, fileUuid, toLoc, pathId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return false;
      }

      // "/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(quote(datcore_uuid, safe=''),
      let fileName = fileUuid.split("/");
      fileName = fileName[fileName.length-1];

      const params = {
        url: {
          toLoc,
          fileName: encodeURIComponent(pathId + "/" + fileName),
          fromLoc,
          fileUuid: encodeURIComponent(fileUuid)
        }
      };
      osparc.data.Resources.fetch("storageFiles", "put", params)
        .then(files => {
          const data = {
            data: files,
            locationId: toLoc,
            fileUuid: pathId + "/" + fileName
          };
          this.fireDataEvent("fileCopied", data);
        })
        .catch(err => {
          console.error(err);
          console.error("Failed copying file", fileUuid, "to", pathId);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed copying file"), "ERROR");
          this.fireDataEvent("fileCopied", null);
        });

      return true;
    },

    deleteFile: function(locationId, fileUuid) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.data.delete", true)) {
        return false;
      }

      // Deletes File
      const params = {
        url: {
          locationId,
          fileUuid: encodeURIComponent(fileUuid)
        }
      };
      osparc.data.Resources.fetch("storageFiles", "delete", params)
        .then(files => {
          const data = {
            data: files,
            locationId: locationId,
            fileUuid: fileUuid
          };
          this.fireDataEvent("deleteFile", data);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed deleting file"), "ERROR");
          this.fireDataEvent("deleteFile", null);
        });

      return true;
    }
  }
});
