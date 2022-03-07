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

    this._setLayout(new qx.ui.layout.VBox(10));

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
    "itemSelected": "qx.event.type.Event"
  },

  statics: {
    getOutput: function(outputs) {
      if ("outFile" in outputs && "value" in outputs["outFile"]) {
        return outputs["outFile"]["value"];
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
          const splitFilename = outFileValue.path.split("/");
          return splitFilename[splitFilename.length-1];
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

    __setOutputValue: function(node, outputValue) {
      node.setOutputData({
        "outFile": outputValue
      });
      const outputs = node.getOutputs();
      const outLabel = osparc.file.FilePicker.getOutputLabel(outputs);
      if (outLabel) {
        node.setLabel(outputValue.label);
      }
      node.getStatus().setProgress(outputValue ? 100 : 0);
    },

    setOutputValueFromStore: function(node, store, dataset, path, label) {
      if (store !== undefined && path) {
        // eslint-disable-next-line no-underscore-dangle
        osparc.file.FilePicker.__setOutputValue(node, {
          store,
          dataset,
          path,
          label
        });
      }
    },

    __setOutputValueFromLink: function(node, downloadLink, label) {
      if (downloadLink) {
        // eslint-disable-next-line no-underscore-dangle
        osparc.file.FilePicker.__setOutputValue(node, {
          downloadLink,
          label: label ? label : ""
        });
      }
    },

    resetOutputValue: function(node) {
      // eslint-disable-next-line no-underscore-dangle
      osparc.file.FilePicker.__setOutputValue(node, null);
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
      this.self().getOutputFileMetadata(node)
        .then(fileMetadata => {
          for (let [key, value] of Object.entries(fileMetadata)) {
            const entry = new qx.ui.form.TextField();
            form.add(entry, key, null, key);
            if (value) {
              entry.setValue(value.toString());
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

    downloadOutput: function(node) {
      if (osparc.file.FilePicker.isOutputFromStore(node.getOutputs())) {
        this.self().getOutputFileMetadata(node)
          .then(fileMetadata => {
            if ("location_id" in fileMetadata && "file_id" in fileMetadata) {
              const locationId = fileMetadata["location_id"];
              const fileId = fileMetadata["file_id"];
              osparc.utils.Utils.retrieveURLAndDownload(locationId, fileId);
            }
          });
      } else if (osparc.file.FilePicker.isOutputDownloadLink(node.getOutputs())) {
        const outFileValue = osparc.file.FilePicker.getOutput(node.getOutputs());
        if (osparc.utils.Utils.isObject(outFileValue) && "downloadLink" in outFileValue) {
          osparc.utils.Utils.downloadLink(outFileValue["downloadLink"], "GET");
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
    }
  },

  members: {
    __filesTree: null,
    __folderViewer: null,
    __selectButton: null,
    __selectedFileLayout: null,
    __selectedFileFound: null,
    __fileDownloadLink: null,

    setOutputValueFromStore: function(store, dataset, path, label) {
      this.self().setOutputValueFromStore(this.getNode(), store, dataset, path, label);
    },

    __setOutputValueFromLink: function(downloadLink, label) {
      // eslint-disable-next-line no-underscore-dangle
      this.self().__setOutputValueFromLink(this.getNode(), downloadLink, label);
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
      this.__addProgressBar();
      const isWorkbenchContext = this.getPageContext() === "workbench";
      if (isWorkbenchContext && osparc.file.FilePicker.hasOutputAssigned(this.getNode().getOutputs())) {
        this.__buildInfoLayout();
      } else if (isWorkbenchContext) {
        this.__buildDropLayout();
      } else {
        this.__buildTreeLayout();
      }
    },

    __addProgressBar: function() {
      const progressBar = new qx.ui.indicator.ProgressBar();
      const nodeStatus = this.getNode().getStatus();
      nodeStatus.bind("progress", progressBar, "value", {
        converter: val => osparc.data.model.NodeStatus.getValidProgress(val)
      });
      nodeStatus.bind("progress", progressBar, "visibility", {
        converter: val => {
          const validProgress = osparc.data.model.NodeStatus.getValidProgress(val);
          return (validProgress > 0 && validProgress < 100) ? "visible" : "excluded";
        }
      });
      this._add(progressBar);
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
      const downloadFileBtn = new qx.ui.form.Button(this.tr("Download"), "@FontAwesome5Solid/cloud-download-alt/14").set({
        allowGrowX: false
      });
      downloadFileBtn.addListener("execute", () => osparc.file.FilePicker.downloadOutput(node));
      hbox.add(downloadFileBtn);
      const resetFileBtn = new qx.ui.form.Button(this.tr("Reset"), "@FontAwesome5Solid/sync-alt/14").set({
        allowGrowX: false
      });
      resetFileBtn.addListener("execute", () => {
        osparc.file.FilePicker.resetOutputValue(node);
        node.setLabel("File Picker");
        node.getStudy().getWorkbench().giveUniqueNameToNode(node, "File Picker");
        this.fireEvent("itemReset");
      }, this);
      hbox.add(resetFileBtn);
      this._add(hbox);
    },

    __buildDropLayout: function() {
      const node = this.getNode();

      const fileDrop = new osparc.file.FileDrop().set({
        allowGrowY: true,
        minHeight: 400
      });
      fileDrop.addListener("localFileDropped", e => {
        const files = e.getData()["data"];
        if (this.uploadPendingFiles(files)) {
          setTimeout(() => this.fireEvent("itemSelected"), 500);
        }
        fileDrop.resetDropAction();
      });
      fileDrop.addListener("fileLinkDropped", e => {
        const data = e.getData()["data"];
        osparc.file.FilePicker.setOutputValueFromStore(node, data.getLocation(), data.getDatasetId(), data.getFileId(), data.getLabel());
        this.fireEvent("itemSelected");
        fileDrop.resetDropAction();
      });

      this._add(fileDrop, {
        flex: 1
      });


      this.__addDownloadLinkSection();
    },

    __addDownloadLinkSection: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5).set({
        alignY: "middle"
      }));

      layout.add(new qx.ui.basic.Label(this.tr("Or provide a Download Link")));

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

      this._add(layout);
    },

    __buildTreeLayout: function() {
      const reloadButton = new qx.ui.form.Button().set({
        label: this.tr("Reload"),
        icon: "@FontAwesome5Solid/sync-alt/16",
        allowGrowX: false
      });
      this._add(reloadButton);
      reloadButton.addListener("execute", () => this.__reloadFilesTree(), this);

      const treeFolderLayout = new qx.ui.splitpane.Pane("horizontal");
      treeFolderLayout.getChildControl("splitter").set({
        width: 2
      });
      const filesTree = this.__filesTree = new osparc.file.FilesTree().set({
        backgroundColor: "background-main-3",
        showLeafs: false,
        minWidth: 150,
        width: 250
      });
      treeFolderLayout.add(filesTree, 0);
      const folderViewer = this.__folderViewer = new osparc.file.FolderViewer();
      treeFolderLayout.add(folderViewer, 1);
      this._add(treeFolderLayout, {
        flex: 1
      });

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


      const mainButtonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      this._add(mainButtonsLayout);

      const fileUploader = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const input = new qx.html.Input("file", {
        display: "none"
      });
      fileUploader.getContentElement().add(input);
      const btn = new qx.ui.toolbar.Button(this.tr("Upload"), "@FontAwesome5Solid/cloud-upload-alt/16");
      btn.addListener("execute", () => input.getDomElement().click());
      input.addListener("change", () => {
        input.getDomElement().files.forEach(file => this.__retrieveUrlAndUpload(file));
      }, this);
      mainButtonsLayout.add(fileUploader);

      const selectedFileLayout = this.__selectedFileLayout = new osparc.file.FileLabelWithActions().set({
        alignY: "middle"
      });
      selectedFileLayout.getChildControl("delete-button").exclude();
      mainButtonsLayout.add(selectedFileLayout, {
        flex: 1
      });

      const selectBtn = this.__selectButton = new qx.ui.form.Button(this.tr("Select"));
      selectBtn.setEnabled(false);
      selectBtn.addListener("execute", () => this.__itemSelected(), this);
      mainButtonsLayout.add(selectBtn);

      this.__addDownloadLinkSection();
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

    __selectionChanged: function(selectedItem) {
      const isFile = osparc.file.FilesTree.isFile(selectedItem);
      if (this.__selectButton) {
        this.__selectButton.setEnabled(isFile);
      }

      this.__selectedFileLayout.setItemSelected(selectedItem);
    },

    __itemSelected: function() {
      const selectedItem = this.__selectedFileLayout.getItemSelected();
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
      const dataStore = osparc.store.Data.getInstance();
      dataStore.getPresignedLink(download, locationId, fileUuid)
        .then(presignedLinkData => {
          if (presignedLinkData.presignedLink) {
            this.__uploadFile(file, presignedLinkData);
          }
        });
    },

    // Use XMLHttpRequest to upload the file to S3.
    __uploadFile: function(file, presignedLinkData) {
      const location = presignedLinkData.locationId;
      const path = presignedLinkData.fileUuid;
      const url = presignedLinkData.presignedLink.link;

      // From https://github.com/minio/cookbook/blob/master/docs/presigned-put-upload-via-browser.md
      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", e => {
        if (e.lengthComputable) {
          const percentComplete = e.loaded / e.total * 100;
          this.getNode().getStatus().setProgress(percentComplete === 100 ? 99 : percentComplete);
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      xhr.onload = () => {
        if (xhr.status == 200) {
          console.log("Uploaded", file.name);
          this.getNode().getStatus().setProgress(100);
          const fileMetadata = {
            location,
            dataset: this.getNode().getStudy().getUuid(),
            path: path,
            name: file.name
          };
          if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
            this.setOutputValueFromStore(fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
          }
          this.__reloadFilesTree();
          if (this.__filesTree) {
            this.__filesTree.loadFilePath(this.__getOutputFile()["value"]);
          }
        } else {
          console.log(xhr.response);
          this.getNode().getStatus().setProgress(0);
        }
      };
      xhr.open("PUT", url, true);
      this.getNode().getStatus().setProgress(0);
      xhr.send(file);
    }
  }
});
