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
  type: "singleton",

  construct: function() {
    this.resetCache();

    this.getLocations();
  },

  events: {
    "fileCopied": "qx.event.type.Data",
  },

  members: {
    __filesByLocationAndDatasetCached: null,

    resetCache: function() {
      this.__filesByLocationAndDatasetCached = {};
    },

    getLocations: function() {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("storageLocations", "getLocations")
          .then(locations => {
            resolve(locations);
          })
          .catch(err => {
            console.error(err);
            reject([]);
          });
      });
    },

    getDatasetsByLocation: function(locationId) {
      const data = {
        location: locationId,
        datasets: []
      };
      return new Promise((resolve, reject) => {
        if (locationId === 1 && !osparc.data.Permissions.getInstance().canDo("storage.datcore.read")) {
          reject(data);
        }

        const params = {
          url: {
            locationId
          }
        };
        osparc.data.Resources.fetch("storagePaths", "getDatasets", params)
          .then(pagResp => {
            if (pagResp["items"] && pagResp["items"].length>0) {
              data.datasets = pagResp["items"];
            }
            resolve(data);
          })
          .catch(err => {
            console.error(err);
            reject(data);
          });
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
      const emptyData = {
        location: locationId,
        dataset: datasetId,
        files: []
      };
      return new Promise((resolve, reject) => {
        // Get list of file meta data
        if (locationId === 1 && !osparc.data.Permissions.getInstance().canDo("storage.datcore.read")) {
          reject(emptyData);
        }

        const cachedData = this.getFilesByLocationAndDatasetCached(locationId, datasetId);
        if (cachedData) {
          resolve(cachedData);
        } else {
          const params = {
            url: {
              locationId: locationId,
              path: datasetId
            }
          };
          osparc.data.Resources.fetch("storagePaths", "getFiles", params)
            .then(pagResp => {
              const data = {
                location: locationId,
                dataset: datasetId,
                files: []
              };
              if (pagResp["items"] && pagResp["items"].length>0) {
                data.files = pagResp["items"];
              }
              // Add it to cache
              if (!(locationId in this.__filesByLocationAndDatasetCached)) {
                this.__filesByLocationAndDatasetCached[locationId] = {};
              }
              this.__filesByLocationAndDatasetCached[locationId][datasetId] = data.files;
              resolve(data);
            })
            .catch(err => {
              console.error(err);
              reject(emptyData);
            });
        }
      });
    },

    getNodeFiles: function(nodeId) {
      return new Promise((resolve, reject) => {
        const nodePath = encodeURIComponent(nodeId);
        const params = {
          url: {
            locationId: 0,
            path: nodePath,
          }
        };
        osparc.data.Resources.fetch("storagePaths", "getFiles", params)
          .then(files => {
            console.log("Node Files", files);
            if (files && files.length>0) {
              resolve(files);
            } else {
              resolve([]);
            }
          })
          .catch(err => {
            console.error(err);
            reject([]);
          });
      });
    },

    getPresignedLink: function(download = true, locationId, fileUuid, fileSize) {
      return new Promise((resolve, reject) => {
        if (download && !osparc.data.Permissions.getInstance().canDo("study.node.data.pull", true)) {
          reject();
        }
        if (!download && !osparc.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
          reject();
        }

        // GET: Returns download link for requested file
        // PUT: Returns upload object link(s)
        const params = {
          url: {
            locationId,
            fileUuid: encodeURIComponent(fileUuid)
          }
        };
        if (!download && fileSize) {
          params.url["fileSize"] = fileSize;
        }
        osparc.data.Resources.fetch("storageLink", download ? "getOne" : "put", params)
          .then(data => {
            const presignedLinkData = {
              resp: data,
              locationId,
              fileUuid,
              fileSize
            };
            resolve(presignedLinkData);
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
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
          osparc.FlashMessenger.getInstance().logAs(this.tr("Failed copying file"), "ERROR");
          this.fireDataEvent("fileCopied", null);
        });

      return true;
    },

    // if folder path is provided as fileUuid, it can also be deleted
    deleteFile: function(locationId, fileUuid) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.data.delete", true)) {
        return null;
      }

      // Deletes File
      const params = {
        url: {
          locationId,
          fileUuid: encodeURIComponent(fileUuid)
        }
      };
      return osparc.data.Resources.fetch("storageFiles", "delete", params)
        .then(files => {
          const data = {
            data: files,
            locationId: locationId,
            fileUuid: fileUuid
          };
          return data;
        })
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(this.tr("Failed deleting file"), "ERROR");
        });
    }
  }
});
