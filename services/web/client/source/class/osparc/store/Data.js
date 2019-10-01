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
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *    const filesStore = osparc.store.Data.getInstance();
 *    filesStore.addListenerOnce("nodeFiles", e => {
 *      const files = e.getData();
 *      const newChildren = osparc.data.Converters.fromDSMToVirtualTreeModel(files);
 *      this.__filesToRoot(newChildren);
 *    }, this);
 *    filesStore.getNodeFiles(nodeId);
 * </pre>
 */

qx.Class.define("osparc.store.Data", {
  extend: qx.core.Object,

  type : "singleton",

  construct: function() {
    this.resetCache();
  },

  events: {
    "myLocations": "qx.event.type.Data",
    "myDatasets": "qx.event.type.Data",
    "myDocuments": "qx.event.type.Data",
    "nodeFiles": "qx.event.type.Data",
    "fileCopied": "qx.event.type.Data",
    "deleteFile": "qx.event.type.Data"
  },

  members: {
    __locationsCached: null,
    __datasetsByLocationCached: null,
    __filesByLocationAndDatasetCached: null,

    resetCache: function() {
      this.__locationsCached = [];
      this.__datasetsByLocationCached = {};
      this.__filesByLocationAndDatasetCached = {};
    },

    getLocationsCached: function() {
      const cache = this.__locationsCached;
      if (cache.length) {
        return cache;
      }
      return null;
    },

    getLocations: function() {
      // Get available storage locations
      const cachedData = this.getLocationsCached();
      if (cachedData) {
        this.fireDataEvent("myLocations", cachedData);
        return;
      }

      const reqLoc = new osparc.io.request.ApiRequest("/storage/locations", "GET");

      reqLoc.addListener("success", eLoc => {
        const locations = eLoc.getTarget().getResponse()
          .data;
        // Add it to cache
        this.__locationsCached = locations;
        this.fireDataEvent("myLocations", locations);
      }, this);

      reqLoc.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        this.fireDataEvent("myLocations", []);
        console.error("Failed getting Storage Locations", error);
      });

      reqLoc.send();
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
        this.fireDataEvent("myDatasets", cachedData);
        return;
      }

      const endPoint = "/storage/locations/" + locationId + "/datasets";
      const reqDatasets = new osparc.io.request.ApiRequest(endPoint, "GET");

      reqDatasets.addListener("success", eFiles => {
        const datasets = eFiles.getTarget().getResponse()
          .data;
        const data = {
          location: locationId,
          datasets: []
        };
        if (datasets && datasets.length>0) {
          data.datasets = datasets;
        }
        // Add it to cache
        this.__datasetsByLocationCached[locationId] = data.datasets;
        this.fireDataEvent("myDatasets", data);
      }, this);

      reqDatasets.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        const data = {
          location: locationId,
          datasets: []
        };
        this.fireDataEvent("myDatasets", data);
        console.error("Failed getting Datasets list", error);
      });

      reqDatasets.send();
    },

    getFilesByLocationAndDatasetCached: function(locationId, datasetId) {
      const cache = this.__filesByLocationAndDatasetCached;
      if (locationId in cache && datasetId in cache[locationId] && cache[locationId][datasetId].length) {
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
        this.fireDataEvent("myDocuments", cachedData);
        return;
      }

      const endPoint = "/storage/locations/" + locationId + "/datasets/" + datasetId + "/metadata";
      const reqFiles = new osparc.io.request.ApiRequest(endPoint, "GET");

      reqFiles.addListener("success", eFiles => {
        const files = eFiles.getTarget().getResponse()
          .data;
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
        this.fireDataEvent("myDocuments", data);
      }, this);

      reqFiles.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        const data = {
          location: locationId,
          dataset: datasetId,
          files: []
        };
        this.fireDataEvent("myDocuments", data);
        console.error("Failed getting Files list", error);
      });

      reqFiles.send();
    },

    getNodeFiles: function(nodeId) {
      const filter = "?uuid_filter=" + encodeURIComponent(nodeId);
      let endPoint = "/storage/locations/0/files/metadata";
      endPoint += filter;
      let reqFiles = new osparc.io.request.ApiRequest(endPoint, "GET");

      reqFiles.addListener("success", eFiles => {
        const files = eFiles.getTarget().getResponse()
          .data;
        console.log("Node Files", files);
        if (files && files.length>0) {
          this.fireDataEvent("nodeFiles", files);
        }
        this.fireDataEvent("nodeFiles", []);
      }, this);

      reqFiles.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        this.fireDataEvent("nodeFiles", []);
        console.error("Failed getting Node Files list", error);
      });

      reqFiles.send();
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
      let res = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + res;
      // const endPoint = "/storage/locations/" + locationId + "/files/" + fileUuid;
      const method = download ? "GET" : "PUT";
      let req = new osparc.io.request.ApiRequest(endPoint, method);

      req.addListener("success", e => {
        const {
          data
        } = e.getTarget().getResponse();
        const presignedLinkData = {
          presignedLink: data,
          locationId: locationId,
          fileUuid: fileUuid
        };
        console.log("presignedLink", presignedLinkData);
        this.fireDataEvent("presignedLink", presignedLinkData);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed getting Presigned Link", error);
      });

      req.send();
    },

    copyFile: function(fromLoc, fileUuid, toLoc, pathId) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return false;
      }

      // "/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(quote(datcore_uuid, safe=''),
      let fileName = fileUuid.split("/");
      fileName = fileName[fileName.length-1];
      let endPoint = "/storage/locations/"+toLoc+"/files/";
      let parameters = encodeURIComponent(pathId + "/" + fileName);
      parameters += "?extra_location=";
      parameters += fromLoc;
      parameters += "&extra_source=";
      parameters += encodeURIComponent(fileUuid);
      endPoint += parameters;
      let req = new osparc.io.request.ApiRequest(endPoint, "PUT");

      req.addListener("success", e => {
        const data = {
          data: e.getTarget().getResponse(),
          locationId: toLoc,
          fileUuid: pathId + "/" + fileName
        };
        this.fireDataEvent("fileCopied", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error(error);
        console.error("Failed copying file", fileUuid, "to", pathId);
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed copying file"), "ERROR");
        this.fireDataEvent("fileCopied", null);
      });

      req.send();

      return true;
    },

    deleteFile: function(locationId, fileUuid) {
      if (!osparc.data.Permissions.getInstance().canDo("study.node.data.delete", true)) {
        return false;
      }

      // Deletes File
      let parameters = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + parameters;
      let req = new osparc.io.request.ApiRequest(endPoint, "DELETE");

      req.addListener("success", e => {
        const data = {
          data: e.getTarget().getResponse(),
          locationId: locationId,
          fileUuid: fileUuid
        };
        this.fireDataEvent("deleteFile", data);
      }, this);

      req.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        console.error("Failed deleting file", error);
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed deleting file"), "ERROR");
        this.fireDataEvent("deleteFile", null);
      });

      req.send();

      return true;
    }
  }
});
