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
 * Built-in service used for selecting a single file from storage and make it available in the workflow
 *
 *   It consists of a widget containing a FilesTree, Add button and Select button:
 * - FilesTree will be populated with data provided by storage service (simcore.S3 and datcore)
 * - Add button will open a dialogue where the selected file will be upload to S3
 * - Select button puts the file in the output of the FilePicker node so that connected nodes can access it.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filePicker = new osparc.file.FilePicker(node);
 *   this.getRoot().add(filePicker);
 * </pre>
 */

qx.Class.define("osparc.file.FilePicker", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node, pageContext = "workbench") {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(20));

    this.set({
      node,
      pageContext
    });

    this.__buildLayout();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    },

    pageContext: {
      check: ["workbench", "guided", "app"],
      nullable: false
    }
  },

  events: {
    "itemReset": "qx.event.type.Event",
    "itemSelected": "qx.event.type.Event",
    "fileUploaded": "qx.event.type.Event"
  },

  statics: {
    getOutput: function(outputs) {
      return osparc.data.model.Node.getOutput(outputs, "outFile");
    },

    getFilenameFromPath: function(output) {
      if ("path" in output) {
        const splitFilename = output.path.split("/");
        return splitFilename[splitFilename.length-1];
      }
      return null;
    },

    getOutputLabel: function(outputs) {
      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      if (outFileValue) {
        if ("label" in outFileValue) {
          return outFileValue.label;
        }
        if ("path" in outFileValue) {
          return this.self().getFilenameFromPath(outFileValue);
        }
        if ("downloadLink" in outFileValue) {
          return osparc.file.FileDownloadLink.extractLabelFromLink(outFileValue["downloadLink"]);
        }
      }
      return null;
    },

    isOutputFromStore: function(outputs) {
      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      return (osparc.utils.Utils.isObject(outFileValue) && "path" in outFileValue);
    },

    isOutputDownloadLink: function(outputs) {
      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      return (osparc.utils.Utils.isObject(outFileValue) && "downloadLink" in outFileValue);
    },

    extractLabelFromLink: function(outputs) {
      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      return osparc.file.FileDownloadLink.extractLabelFromLink(outFileValue["downloadLink"]);
    },

    hasOutputAssigned: function(outputs) {
      return osparc.file.FilePicker.isOutputFromStore(outputs) || osparc.file.FilePicker.isOutputDownloadLink(outputs);
    },

    setOutputValue: function(node, outputValue) {
      node.setOutputData({
        "outFile": outputValue
      });
      const outputs = node.getOutputs();
      const outLabel = osparc.file.FilePicker.getOutputLabel(outputs);
      if (outLabel && node.getLabel().includes("File Picker")) {
        node.setLabel(outputValue.label);
      }
      node.getStatus().setProgress(outputValue ? 100 : 0);
    },

    setOutputValueFromStore: function(node, store, dataset, path, label) {
      if (store !== undefined && path) {
        osparc.file.FilePicker.setOutputValue(node, {
          store,
          dataset,
          path,
          label
        });
      }
    },

    setOutputValueFromLink: function(node, downloadLink, label) {
      if (downloadLink) {
        osparc.file.FilePicker.setOutputValue(node, {
          downloadLink,
          label: label ? label : ""
        });
      }
    },

    resetOutputValue: function(node) {
      osparc.file.FilePicker.setOutputValue(node, null);
    },

    getOutputFileMetadata: function(node) {
      return new Promise((resolve, reject) => {
        const outValue = osparc.file.FilePicker.getOutput(node.getOutputs());
        const params = {
          url: {
            locationId: outValue.store,
            datasetId: outValue.dataset
          }
        };
        osparc.data.Resources.fetch("storageFiles", "getByLocationAndDataset", params)
          .then(files => {
            const fileMetadata = files.find(file => file.file_id === outValue.path);
            if (fileMetadata) {
              resolve(fileMetadata);
            } else {
              reject();
            }
          })
          .catch(() => reject());
      });
    },

    buildFileFromStoreInfoView: function(node, form) {
      const showFields = ["file_name", "file_size", "last_modified"];
      this.self().getOutputFileMetadata(node)
        .then(fileMetadata => {
          for (let [key, value] of Object.entries(fileMetadata)) {
            if (osparc.data.Permissions.getInstance().canDo("services.filePicker.read.all") || showFields.includes(key)) {
              const entry = new qx.ui.form.TextField();
              form.add(entry, key, null, key);
              if (value) {
                if (key === "file_size") {
                  const val = osparc.utils.Utils.bytesToSize(value);
                  entry.setValue(val);
                } else if (key === "last_modified") {
                  const val = osparc.utils.Utils.formatDateAndTime(new Date(value));
                  entry.setValue(val);
                } else {
                  entry.setValue(value.toString());
                }
              }
            }
          }
        });
    },

    buildDownloadLinkInfoView: function(node, form) {
      const outputs = node.getOutputs();

      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      const urlEntry = new qx.ui.form.TextField().set({
        value: outFileValue["downloadLink"]
      });
      form.add(urlEntry, "url", null, "url");

      const label = osparc.file.FilePicker.extractLabelFromLink(outputs);
      if (label) {
        const labelEntry = new qx.ui.form.TextField().set({
          value: label
        });
        form.add(labelEntry, "label", null, "label");
      }
    },

    downloadOutput: function(node, downloadFileBtn) {
      const progressCb = () => downloadFileBtn.setFetching(true);
      const loadedCb = () => downloadFileBtn.setFetching(false);
      if (osparc.file.FilePicker.isOutputFromStore(node.getOutputs())) {
        this.self().getOutputFileMetadata(node)
          .then(fileMetadata => {
            if ("location_id" in fileMetadata && "file_id" in fileMetadata) {
              const locationId = fileMetadata["location_id"];
              const fileId = fileMetadata["file_id"];
              osparc.utils.Utils.retrieveURLAndDownload(locationId, fileId)
                .then(data => {
                  if (data) {
                    osparc.utils.Utils.downloadLink(data.link, "GET", data.fileName, progressCb, loadedCb);
                  }
                });
            }
          });
      } else if (osparc.file.FilePicker.isOutputDownloadLink(node.getOutputs())) {
        const outFileValue = osparc.file.FilePicker.getOutput(node.getOutputs());
        if (osparc.utils.Utils.isObject(outFileValue) && "downloadLink" in outFileValue) {
          osparc.utils.Utils.downloadLink(outFileValue["downloadLink"], "GET", null, progressCb, loadedCb);
        }
      }
    },

    serializeOutput: function(outputs) {
      let output = {};
      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      if (outFileValue) {
        output["outFile"] = outFileValue;
      }
      return output;
    },

    POS: {
      RELOAD: 0,
      FILES_TREE: 1,
      TOOLBAR: 2,
      DOWNLOAD_LINK: 3
    },

    PROGRESS_VALUES: {
      NOTHING: 0,
      FETCHING_PLINK: 1,
      CHUNKING: 2,
      COMPLETING: 99
    }
  },

  members: {
    __filesTree: null,
    __selectButton: null,
    __selectedFile: null,
    __selectedFileFound: null,
    __fileDownloadLink: null,
    __uploadedParts: null,

    setOutputValueFromStore: function(store, dataset, path, label) {
      this.self().setOutputValueFromStore(this.getNode(), store, dataset, path, label);
    },

    __setOutputValueFromLink: function(downloadLink, label) {
      this.self().setOutputValueFromLink(this.getNode(), downloadLink, label);
    },

    __reloadFilesTree: function() {
      if (this.__filesTree) {
        this.__selectedFileFound = false;
        this.__filesTree.resetCache();
        this.__filesTree.populateTree();
      }
    },

    __buildLayout: function() {
      this._removeAll();
      const isWorkbenchContext = this.getPageContext() === "workbench";
      const hasOutput = osparc.file.FilePicker.hasOutputAssigned(this.getNode().getOutputs());
      if (isWorkbenchContext) {
        if (hasOutput) {
          // WORKBENCH mode WITH output
          this.__buildInfoLayout();
        } else {
          // WORKBENCH mode WITHOUT output
          this.__addProgressBar();
          this.__buildNoFileWBLayout();
        }
      } else {
        this.setMargin(10);
        if (hasOutput) {
          // APP mode WITH output
          this.__buildInfoLayout();
        } else {
          // APP mode WITHOUT output
          this.__addProgressBar();
          this.__buildNoFileAppLayout();
        }
      }
    },

    __addProgressBar: function() {
      const progressLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));

      const progressBar = new qx.ui.indicator.ProgressBar();
      const nodeStatus = this.getNode().getStatus();
      nodeStatus.bind("progress", progressBar, "value", {
        converter: val => osparc.data.model.NodeStatus.getValidProgress(val)
      });
      progressLayout.add(progressBar, {
        flex: 1
      });

      const stopButton = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/times/16",
        toolTipText: this.tr("Cancel upload"),
        appearance: "danger-button",
        allowGrowX: false
      });
      stopButton.addListener("tap", () => this.getNode()["abortRequested"] = true);
      progressLayout.add(stopButton);

      const progressChanged = () => {
        const progress = this.getNode().getStatus().getProgress();
        const validProgress = osparc.data.model.NodeStatus.getValidProgress(progress);
        const uploading = (validProgress > 0 && validProgress < 100);
        progressLayout.setVisibility(uploading ? "visible" : "excluded");
        this._getChildren().forEach(child => {
          if (child !== progressLayout) {
            child.setEnabled(!uploading);
          }
        });
      };
      nodeStatus.addListener("changeProgress", () => progressChanged());
      progressChanged();

      this._add(progressLayout);
    },

    __buildInfoLayout: function() {
      const node = this.getNode();

      const form = new qx.ui.form.Form();
      if (osparc.file.FilePicker.isOutputFromStore(node.getOutputs())) {
        this.self().buildFileFromStoreInfoView(node, form);
      } else if (osparc.file.FilePicker.isOutputDownloadLink(node.getOutputs())) {
        this.self().buildDownloadLinkInfoView(node, form);
      }
      const formRend = new qx.ui.form.renderer.Single(form);
      formRend.setEnabled(false);
      this._add(formRend);

      const hbox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const downloadFileBtn = this.__getDownloadFileButton();
      hbox.add(downloadFileBtn);
      const resetFileBtn = this.__getResetFileButton();
      hbox.add(resetFileBtn);
      this._add(hbox);
    },

    __getDownloadFileButton: function() {
      const node = this.getNode();
      const downloadFileBtn = new osparc.ui.form.FetchButton(this.tr("Download"), "@FontAwesome5Solid/cloud-download-alt/14").set({
        allowGrowX: false
      });
      downloadFileBtn.addListener("execute", () => osparc.file.FilePicker.downloadOutput(node, downloadFileBtn));
      return downloadFileBtn;
    },

    __getResetFileButton: function() {
      const node = this.getNode();
      const resetFileBtn = new qx.ui.form.Button(this.tr("Reset"), "@FontAwesome5Solid/sync-alt/14").set({
        allowGrowX: false
      });
      resetFileBtn.addListener("execute", () => {
        osparc.file.FilePicker.resetOutputValue(node);
        this.fireEvent("itemReset");
      }, this);
      return resetFileBtn;
    },

    __buildNoFileWBLayout: function() {
      const uploadFileSection = this.__getUploadFileSection();
      this._add(uploadFileSection);

      const fileDrop = this.__getFileDropSection();
      this._add(fileDrop, {
        flex: 1
      });

      const downloadLinkSection = this.__getDownloadLinkSection();
      this._add(downloadLinkSection);
    },

    __getUploadFileSection: function() {
      const uploadFileSection = new osparc.ui.form.FileInput();
      uploadFileSection.addListener("selectionChanged", () => {
        const file = uploadFileSection.getFile();
        if (file) {
          if (this.uploadPendingFiles([file])) {
            setTimeout(() => this.fireEvent("itemSelected"), 500);
          }
        }
      });
      return uploadFileSection;
    },

    __getFileDropSection: function() {
      const fileDrop = new osparc.file.FileDrop();
      fileDrop.addListener("localFileDropped", e => {
        const files = e.getData()["data"];
        if (this.uploadPendingFiles(files)) {
          setTimeout(() => this.fireEvent("itemSelected"), 500);
        }
        fileDrop.resetDropAction();
      });
      fileDrop.addListener("fileLinkDropped", e => {
        const data = e.getData()["data"];
        const node = this.getNode();
        osparc.file.FilePicker.setOutputValueFromStore(node, data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
        this.fireEvent("itemSelected");
        fileDrop.resetDropAction();
      });
      return fileDrop;
    },

    __getDownloadLinkSection: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      layout.add(new qx.ui.basic.Label(this.tr("Provide Link")));

      const fileDownloadLink = this.__fileDownloadLink = new osparc.file.FileDownloadLink().set({
        allowGrowY: false
      });
      fileDownloadLink.addListener("fileLinkAdded", e => {
        const downloadLink = e.getData();
        const label = osparc.file.FileDownloadLink.extractLabelFromLink(downloadLink);
        this.__setOutputValueFromLink(downloadLink, label);
        this.fireEvent("itemSelected");
      }, this);
      layout.add(fileDownloadLink);

      return layout;
    },

    __buildNoFileAppLayout: function() {
      let msg = this.tr("In order to Select a file you have three options:");
      const options = [
        this.tr("- Upload a file"),
        this.tr("- Select a file from tree"),
        this.tr("- Provide Link")
      ];
      for (let i=0; i<options.length; i++) {
        msg += "<br>" + options[i];
      }
      const intro = new qx.ui.basic.Label(msg).set({
        font: "text-16",
        rich: true
      });
      this._add(intro);

      const uploadFileSection = this.__getUploadFileSection();
      this._add(uploadFileSection);

      const fileBrowserLayout = this.__getFileBrowserLayout();
      this._add(fileBrowserLayout, {
        flex: 1
      });

      const downloadLinkSection = this.__getDownloadLinkSection();
      this._add(downloadLinkSection);
    },

    __getFileBrowserLayout: function() {
      const treeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const reloadButton = new qx.ui.form.Button().set({
        label: this.tr("Reload"),
        icon: "@FontAwesome5Solid/sync-alt/16",
        allowGrowX: false
      });
      reloadButton.addListener("execute", () => this.__reloadFilesTree(), this);
      treeLayout.add(reloadButton);

      const treeFolderLayout = new qx.ui.splitpane.Pane("horizontal");
      treeFolderLayout.getChildControl("splitter").set({
        width: 2
      });
      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        backgroundColor: "background-main-2",
        showLeafs: false,
        minWidth: 150,
        width: 250
      });
      treeLayout.add(filesTree, {
        flex: 1
      });
      treeFolderLayout.add(treeLayout, 0);
      const folderViewer = new osparc.file.FolderViewer();
      treeFolderLayout.add(folderViewer, 1);

      filesTree.addListener("selectionChanged", () => {
        const selectionData = filesTree.getSelectedItem();
        this.__selectionChanged(selectionData);
        if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
          folderViewer.setFolder(selectionData);
        }
      }, this);
      filesTree.addListener("filesAddedToTree", () => this.__checkSelectedFileIsListed(), this);
      this.__reloadFilesTree();

      folderViewer.addListener("selectionChanged", e => {
        const selectionData = e.getData();
        this.__selectionChanged(selectionData);
      }, this);
      folderViewer.addListener("itemSelected", e => {
        const selectionData = e.getData();
        this.__selectionChanged(selectionData);
        if (osparc.file.FilesTree.isFile(selectionData)) {
          this.__itemSelected();
        } else if (osparc.file.FilesTree.isDir(selectionData)) {
          filesTree.openNodeAndParents(selectionData);
          filesTree.setSelection(new qx.data.Array([selectionData]));
        }
      }, this);
      folderViewer.addListener("folderUp", e => {
        const currentFolder = e.getData();
        const parent = filesTree.getParent(currentFolder);
        if (parent) {
          filesTree.setSelection(new qx.data.Array([parent]));
          folderViewer.setFolder(parent);
        }
      }, this);
      folderViewer.addListener("requestDatasetFiles", e => {
        const data = e.getData();
        filesTree.requestDatasetFiles(data.locationId, data.datasetId);
      }, this);

      const selectBtn = this.__selectButton = new qx.ui.form.Button(this.tr("Select")).set({
        allowGrowX: false,
        alignX: "right"
      });
      selectBtn.setEnabled(false);
      selectBtn.addListener("execute", () => this.__itemSelected(), this);
      // eslint-disable-next-line no-underscore-dangle
      folderViewer._add(selectBtn);

      return treeFolderLayout;
    },

    init: function() {
      if (this.self().isOutputFromStore(this.getNode().getOutputs())) {
        const outFile = this.__getOutputFile();
        this.__filesTree.loadFilePath(outFile.value);
      }

      if (this.self().isOutputDownloadLink(this.getNode().getOutputs())) {
        const outFile = this.__getOutputFile();
        if (this.__fileDownloadLink) {
          this.__fileDownloadLink.setValue(outFile.value["downloadLink"]);
        }
      }
    },

    uploadPendingFiles: function(files) {
      if (files.length > 0) {
        if (files.length === 1) {
          this.__retrieveUrlAndUpload(files[0]);
          return true;
        }
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
      }
      return false;
    },

    __selectionChanged: function(selectedData) {
      this.__selectedFile = selectedData;
      const isFile = osparc.file.FilesTree.isFile(selectedData);
      if (this.__selectButton) {
        this.__selectButton.setEnabled(isFile);
      }
    },

    __itemSelected: function() {
      const selectedItem = this.__selectedFile;
      if (selectedItem && osparc.file.FilesTree.isFile(selectedItem)) {
        this.setOutputValueFromStore(selectedItem.getLocation(), selectedItem.getDatasetId(), selectedItem.getFileId(), selectedItem.getLabel());
        this.fireEvent("itemSelected");
      }
    },

    __getOutputFile: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFile"];
    },

    __checkSelectedFileIsListed: function() {
      if (this.__selectedFileFound === false && this.self().isOutputFromStore(this.getNode().getOutputs())) {
        const outFile = this.__getOutputFile();
        const selected = this.__filesTree.setSelectedFile(outFile.value.path);
        if (selected) {
          this.__selectedFileFound = true;
          this.__filesTree.fireEvent("selectionChanged");
        }
      }
    },

    // Request to the server an upload URL.
    __retrieveUrlAndUpload: function(file) {
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
            try {
              this.__uploadFile(file, presignedLinkData);
            } catch (error) {
              console.error(error);
              this.__abortUpload(presignedLinkData);
            }
          }
        });
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: async function(file, presignedLinkData) {
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
        if (this.getNode()["abortRequested"]) {
          this.__abortUpload(presignedLinkData);
        }
        const chunkBlob = this.__createChunk(file, fileSize, chunkIdx, chunkSize);
        try {
          const uploaded = await this.__uploadChunk(file, chunkBlob, presignedLinkData, chunkIdx);
          if (!uploaded) {
            this.__abortUpload(presignedLinkData);
          }
        } catch (err) {
          this.__abortUpload(presignedLinkData);
        }
      }
    },

    __uploadChunk: function(file, chunkBlob, presignedLinkData, chunkIdx) {
      return new Promise((resolve, reject) => {
        // From https://github.com/minio/cookbook/blob/master/docs/presigned-put-upload-via-browser.md
        const url = presignedLinkData.resp.urls[chunkIdx];
        const xhr = new XMLHttpRequest();
        xhr.onload = () => {
          if (xhr.status == 200) {
            const eTag = xhr.getResponseHeader("etag");
            if (eTag) {
              // remove double double quotes ""etag"" -> "etag"
              this.__uploadedParts[chunkIdx]["e_tag"] = eTag.slice(1, -1);
              const uploadedParts = this.__uploadedParts.filter(uploadedPart => uploadedPart["e_tag"] !== null).length;
              const progress = uploadedParts/this.__uploadedParts.length;
              // force progress value to be between 1 and 99
              const nProgress = Math.min(Math.max(100*progress-1, 1), 99);
              this.getNode().getStatus().setProgress(nProgress);
              if (this.__uploadedParts.every(uploadedPart => uploadedPart["e_tag"] !== null)) {
                this.__checkCompleteUpload(file, presignedLinkData, xhr);
              }
            }
            resolve(Boolean(eTag));
          } else {
            console.error(xhr.response);
            this.__abortUpload(presignedLinkData);
            reject(xhr.response);
          }
        };
        xhr.open("PUT", url, true);
        xhr.send(chunkBlob);
      });
    },

    __createChunk: function(file, fileSize, chunkIdx, chunkSize) {
      const start = chunkIdx * chunkSize;
      const chunkEnd = Math.min(start + chunkSize, fileSize);
      const chunkBlob = file.slice(start, chunkEnd);
      return chunkBlob;
    },

    // Use XMLHttpRequest to complete the upload to S3
    __checkCompleteUpload: function(file, presignedLinkData) {
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
          this.__abortUpload(presignedLinkData);
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
      this.getNode()["abortRequested"] = false;

      if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
        this.setOutputValueFromStore(fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
      }
      this.__presignedLinkData = null;
      this.fireEvent("fileUploaded");
    },

    __abortUpload: function(presignedLinkData) {
      this.getNode()["abortRequested"] = false;

      this.getNode().getStatus().setProgress(this.self().PROGRESS_VALUES.NOTHING);
      const abortUrl = presignedLinkData.resp.links.abort_upload;
      const xhr = new XMLHttpRequest();
      xhr.open("POST", abortUrl, true);
    }
  }
});
