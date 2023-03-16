/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.file.FileUploader", {
  extend: qx.core.Object,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node
    });

    this.__presignedLinkData = null;
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  events: {
    "uploadAborted": "qx.event.type.Event",
    "fileUploaded": "qx.event.type.Event"
  },

  statics: {
    PROGRESS_VALUES: {
      FETCHING_PLINK: 1,
      CHUNKING: 2,
      COMPLETING: 99
    },

    createChunk: function(file, fileSize, chunkIdx, chunkSize) {
      const start = chunkIdx * chunkSize;
      const chunkEnd = Math.min(start + chunkSize, fileSize);
      const chunkBlob = file.slice(start, chunkEnd);
      return chunkBlob;
    }
  },

  members: {
    __presignedLinkData: null,
    __uploadedParts: null,

    // Request to the server an upload URL.
    retrieveUrlAndUpload: function(file) {
      if (this.getNode() === null) {
        return;
      }

      const download = false;
      const locationId = 0;
      const studyId = this.getNode().getStudy().getUuid();
      const nodeId = this.getNode() ? this.getNode().getNodeId() : osparc.utils.Utils.uuidv4();
      const fileId = file.name;
      const fileUuid = studyId +"/"+ nodeId +"/"+ fileId;
      const fileSize = file.size;
      const dataStore = osparc.store.Data.getInstance();
      this.getNode().getStatus().setProgress(this.self().PROGRESS_VALUES.FETCHING_PLINK);
      dataStore.getPresignedLink(download, locationId, fileUuid, fileSize)
        .then(presignedLinkData => {
          if (presignedLinkData.resp.urls) {
            this.__presignedLinkData = presignedLinkData;
            try {
              this.__uploadFile(file);
            } catch (error) {
              console.error(error);
              this.__abortUpload();
            }
          }
        });
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: async function(file) {
      const presignedLinkData = this.__presignedLinkData;
      this.getNode().getStatus().setProgress(this.self().PROGRESS_VALUES.CHUNKING);

      // create empty object, it will be filled up with etags and 1 based chunk ids when chunks get uploaded
      this.__uploadedParts = [];
      for (let chunkIdx = 0; chunkIdx < presignedLinkData.resp.urls.length; chunkIdx++) {
        this.__uploadedParts.push({
          "number": chunkIdx+1,
          "e_tag": null
        });
      }
      const fileSize = presignedLinkData.fileSize;
      const chunkSize = presignedLinkData.resp["chunk_size"];
      for (let chunkIdx = 0; chunkIdx < presignedLinkData.resp.urls.length; chunkIdx++) {
        if (this.getNode()["requestAbortUpload"]) {
          this.__abortUpload();
          break;
        }
        const chunkBlob = this.self().createChunk(file, fileSize, chunkIdx, chunkSize);
        try {
          const eTag = await this.__uploadChunk(chunkBlob, chunkIdx);
          if (eTag) {
            // remove double double quotes ""e_tag"" -> "e_tag"
            this.__uploadedParts[chunkIdx]["e_tag"] = eTag.slice(1, -1);
            const uploadedParts = this.__uploadedParts.filter(uploadedPart => uploadedPart["e_tag"] !== null).length;
            const progress = uploadedParts/this.__uploadedParts.length;
            // normalize progress value between CHUNKING and COMPLETING
            const min = this.self().PROGRESS_VALUES.CHUNKING;
            const max = this.self().PROGRESS_VALUES.COMPLETING;
            const nProgress = Math.min(Math.max(100*progress-min, min), max);
            this.getNode().getStatus().setProgress(nProgress);
            if (this.__uploadedParts.every(uploadedPart => uploadedPart["e_tag"] !== null)) {
              this.__checkCompleteUpload(file);
            }
          }
        } catch (err) {
          console.error(err);
          this.__abortUpload();
        }
      }
    },

    __uploadChunk: function(chunkBlob, chunkIdx) {
      return new Promise((resolve, reject) => {
        // From https://github.com/minio/cookbook/blob/master/docs/presigned-put-upload-via-browser.md
        const url = this.__presignedLinkData.resp.urls[chunkIdx];
        const xhr = new XMLHttpRequest();
        xhr.onload = () => {
          if (xhr.status == 200) {
            const eTag = xhr.getResponseHeader("etag");
            resolve(eTag);
          } else {
            reject(xhr.response);
          }
        };
        xhr.open("PUT", url, true);
        xhr.send(chunkBlob);
      });
    },

    // Use XMLHttpRequest to complete the upload to S3
    __checkCompleteUpload: function(file) {
      if (this.getNode()["requestAbortUpload"]) {
        this.__abortUpload();
        return;
      }

      const presignedLinkData = this.__presignedLinkData;
      this.getNode().getStatus().setProgress(this.self().PROGRESS_VALUES.COMPLETING);
      const completeUrl = presignedLinkData.resp.links.complete_upload;
      const location = presignedLinkData.locationId;
      const path = presignedLinkData.fileUuid;
      const xhr = new XMLHttpRequest();
      xhr.onloadend = () => {
        const fileMetadata = {
          location,
          dataset: this.getNode().getStudy().getUuid(),
          path,
          name: file.name
        };
        const resp = JSON.parse(xhr.responseText);
        if ("error" in resp && resp["error"]) {
          console.error(resp["error"]);
          this.__abortUpload();
        } else if ("data" in resp) {
          if (xhr.status == 202) {
            console.log("waiting for completion", file.name);
            // @odeimaiz: we need to poll the received new location in the response
            // we do have links.state -> poll that link until it says ok
            // right now this kind of work if files are small and this happens fast
            this.__pollFileUploadState(resp["data"]["links"]["state"], fileMetadata);
          } else if (xhr.status == 200) {
            this.__completeUpload(fileMetadata);
          }
        }
      };
      xhr.open("POST", completeUrl, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      const body = {
        parts: this.__uploadedParts
      };
      xhr.send(JSON.stringify(body));
    },

    __pollFileUploadState: function(stateLink, fileMetadata) {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", stateLink, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.onloadend = () => {
        const resp = JSON.parse(xhr.responseText);
        if ("data" in resp && resp["data"] && resp["data"]["state"] === "ok") {
          this.__completeUpload(fileMetadata);
        } else {
          const interval = 2000;
          qx.event.Timer.once(() => this.__pollFileUploadState(stateLink, fileMetadata), this, interval);
        }
      };
      xhr.send();
    },

    __completeUpload: function(fileMetadata) {
      this.getNode()["requestAbortUpload"] = false;

      if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
        osparc.file.FilePicker.setOutputValueFromStore(this.getNode(), fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
      }
      this.__presignedLinkData = null;
      this.fireEvent("fileUploaded");
    },

    __abortUpload: function() {
      this.getNode()["requestAbortUpload"] = false;

      const aborted = () => {
        this.__presignedLinkData = null;
        // avoid interfering with the progress update
        setTimeout(() => this.fireEvent("uploadAborted"), osparc.desktop.StudyEditor.AUTO_SAVE_INTERVAL);
      };
      const abortUrl = this.__presignedLinkData.resp.links.abort_upload;
      if (abortUrl) {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", abortUrl, true);
        xhr.onload = () => aborted();
        xhr.send();
      } else {
        aborted();
      }
    }
  }
});
