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

/**
 * Singleton class that is used as entrypoint to the webserver.
 *
 * All data transfer communication goes through the qxapp.store.Store.
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *    const filesStore = qxapp.store.Files.getInstance();
 *    filesStore.addListenerOnce("nodeFiles", e => {
 *      const files = e.getData();
 *      const newChildren = qxapp.data.Converters.fromDSMToVirtualTreeModel(files);
 *      this.__filesToRoot(newChildren);
 *    }, this);
 *    filesStore.getNodeFiles(nodeId);
 * </pre>
 */

qx.Class.define("qxapp.store.Data", {
  extend: qx.core.Object,

  type : "singleton",

  construct: function() {
    this.__locationsCached = [];
    this.__datasetsByLocationCached = {};
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

    getLocations: function(useCache = true) {
      // Get available storage locations
      if (useCache && this.__locationsCached.length) {
        this.fireDataEvent("myLocations", this.__locationsCached);
        return;
      }

      const reqLoc = new qxapp.io.request.ApiRequest("/storage/locations", "GET");

      reqLoc.addListener("success", eLoc => {
        const locations = eLoc.getTarget().getResponse()
          .data;
        this.__locations = locations;
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

    getDatasetsByLocation: function(locationId, useCache = true) {
      // Get list of datasets
      if (locationId === 1 && !qxapp.data.Permissions.getInstance().canDo("storage.datcore.read")) {
        return;
      }

      let cache = this.__datasetsByLocationCached;
      if (useCache && locationId in cache && cache[locationId].length) {
        const data = {
          location: locationId,
          datasets: cache[locationId]
        };
        this.fireDataEvent("myDatasets", data);
        return;
      }

      const endPoint = "/storage/locations/" + locationId + "/datasets";
      const reqDatasets = new qxapp.io.request.ApiRequest(endPoint, "GET");

      reqDatasets.addListener("success", eFiles => {
        const datasets = eFiles.getTarget().getResponse()
          .data;
        this.__datasetsByLocationCached = {
          locationId: datasets
        };
        const data = {
          location: locationId,
          datasets: []
        };
        if (datasets && datasets.length>0) {
          data.datasets = datasets;
        }
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

    getFilesByLocation: function(locationId) {
      if (locationId === 1 && !qxapp.data.Permissions.getInstance().canDo("storage.datcore.read")) {
        return;
      }
      // Get list of file meta data
      const endPoint = "/storage/locations/" + locationId + "/files/metadata";
      const reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

      reqFiles.addListener("success", eFiles => {
        const files = eFiles.getTarget().getResponse()
          .data;
        const data = {
          location: locationId,
          files: []
        };
        if (files && files.length>0) {
          data.files = files;
        }
        this.fireDataEvent("myDocuments", data);
      }, this);

      reqFiles.addListener("fail", e => {
        const {
          error
        } = e.getTarget().getResponse();
        const data = {
          location: locationId,
          files: []
        };
        this.fireDataEvent("myDocuments", data);
        console.error("Failed getting Files list", error);
      });

      reqFiles.send();
    },

    getFilesByLocationAndDataset: function(locationId, datasetId) {
      if (locationId === 1 && !qxapp.data.Permissions.getInstance().canDo("storage.datcore.read")) {
        return;
      }
      // Get list of file meta data
      const endPoint = "/storage/locations/" + locationId + "/datasets/" + datasetId + "/metadata";
      const reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

      reqFiles.addListener("success", eFiles => {
        const files = eFiles.getTarget().getResponse()
          .data;
        const data = {
          location: locationId,
          dataset: datasetId,
          files: files && files.length>0 ? files : []
        };
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
      let reqFiles = new qxapp.io.request.ApiRequest(endPoint, "GET");

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
      if (download && !qxapp.data.Permissions.getInstance().canDo("study.node.data.pull", true)) {
        return;
      }
      if (!download && !qxapp.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
        return;
      }

      // GET: Returns download link for requested file
      // POST: Returns upload link or performs copy operation to datcore
      let res = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + res;
      // const endPoint = "/storage/locations/" + locationId + "/files/" + fileUuid;
      const method = download ? "GET" : "PUT";
      let req = new qxapp.io.request.ApiRequest(endPoint, method);

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
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.data.push", true)) {
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
      let req = new qxapp.io.request.ApiRequest(endPoint, "PUT");

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
        qxapp.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed copying file"), "ERROR");
        this.fireDataEvent("fileCopied", null);
      });

      req.send();

      return true;
    },

    deleteFile: function(locationId, fileUuid) {
      if (!qxapp.data.Permissions.getInstance().canDo("study.node.data.delete", true)) {
        return false;
      }

      // Deletes File
      let parameters = encodeURIComponent(fileUuid);
      const endPoint = "/storage/locations/" + locationId + "/files/" + parameters;
      let req = new qxapp.io.request.ApiRequest(endPoint, "DELETE");

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
        qxapp.component.message.FlashMessenger.getInstance().logAs(this.tr("Failed deleting file"), "ERROR");
        this.fireDataEvent("deleteFile", null);
      });

      req.send();

      return true;
    }
  }
});
