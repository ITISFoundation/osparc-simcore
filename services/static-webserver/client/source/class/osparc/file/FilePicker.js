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
        if ("label" in outFileValue && outFileValue["label"]) {
          return outFileValue.label;
        }
        if ("path" in outFileValue && outFileValue["path"]) {
          return this.self().getFilenameFromPath(outFileValue);
        }
        if ("downloadLink" in outFileValue && outFileValue["downloadLink"]) {
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
      } else {
        node.setLabel("File Picker");
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
          osparc.utils.Utils.downloadLink(outFileValue["downloadLink"], "GET", outFileValue["label"], progressCb, loadedCb);
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
    __selectButton: null,
    __selectedFile: null,
    __selectedFileFound: null,
    __fileDownloadLink: null,

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
      const hasOutput = osparc.file.FilePicker.hasOutputAssigned(this.getNode().getOutputs());
      if (hasOutput) {
        this.__buildInfoLayout();
      } else {
        this.__addProgressBar();
        const isWorkbenchContext = this.getPageContext() === "workbench";
        if (isWorkbenchContext) {
          this.__buildWorkbenchLayout();
        } else {
          this.setMargin(10);
          this.__buildAppModeLayout();
        }
      }
    },

    __addProgressBar: function() {
      const progressLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      progressLayout.alwaysEnabled = true;

      const progressBar = new qx.ui.indicator.ProgressBar();
      const nodeStatus = this.getNode().getStatus();
      nodeStatus.bind("progress", progressBar, "value", {
        converter: val => osparc.data.model.NodeStatus.getValidProgress(val)
      });
      progressLayout.add(progressBar, {
        flex: 1
      });

      const stopButton = new osparc.ui.form.FetchButton().set({
        minHeight: 24,
        icon: "@FontAwesome5Solid/times/16",
        toolTipText: this.tr("Cancel upload"),
        appearance: "danger-button",
        allowGrowX: false
      });
      stopButton.addListener("tap", () => {
        stopButton.setFetching(true);
        this.getNode().requestFileUploadAbort();
      });
      progressLayout.add(stopButton);

      const progressChanged = () => {
        const progress = this.getNode().getStatus().getProgress();
        const validProgress = osparc.data.model.NodeStatus.getValidProgress(progress);
        const uploading = (validProgress > 0 && validProgress < 100);
        progressLayout.setVisibility(uploading ? "visible" : "excluded");
        this._getChildren().forEach(child => {
          if (!child.alwaysEnabled) {
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

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      const downloadFileBtn = this.__getDownloadFileButton();
      hBox.add(downloadFileBtn);
      const resetFileBtn = this.__getResetFileButton();
      hBox.add(resetFileBtn);
      this._add(hBox);
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
      const resetFileBtn = new qx.ui.form.Button(this.tr("Reset"), "@FontAwesome5Solid/sync-alt/14").set({
        allowGrowX: false
      });
      resetFileBtn.addListener("execute", () => this.__resetOutput());
      return resetFileBtn;
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

    uploadPendingFiles: function(files) {
      if (files.length > 0) {
        if (files.length === 1) {
          const fileUploader = new osparc.file.FileUploader(this.getNode());
          fileUploader.addListener("uploadAborted", () => this.__resetOutput());
          fileUploader.addListener("fileUploaded", () => {
            this.fireEvent("fileUploaded");
            this.getNode().fireEvent("fileUploaded");
          }, this);
          fileUploader.retrieveUrlAndUpload(files[0]);
          return true;
        }
        osparc.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
      }
      return false;
    },

    __getDownloadLinkSection: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

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

    __buildWorkbenchLayout: function() {
      const uploadFileSection = this.__getUploadFileSection();
      this._add(uploadFileSection);

      const fileDrop = this.__getFileDropSection();
      this._add(fileDrop, {
        flex: 1
      });

      const downloadLinkSection = this.__getDownloadLinkSection();
      this._add(downloadLinkSection);
    },

    __buildAppModeLayout: function() {
      const msg = this.tr("In order to Select a File you have three options:");
      const intro = new qx.ui.basic.Label(msg).set({
        font: "text-16",
        rich: true
      });
      this._add(intro);

      const collapsibleViews = [];
      const contentMargin = 10;

      const newFileSection = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      const uploadFileSection = this.__getUploadFileSection();
      uploadFileSection.getButton().set({
        appearance: "strong-button",
        font: "text-14"
      });
      newFileSection.add(uploadFileSection);
      const fileDrop = this.__getFileDropSection();
      fileDrop.setDropHereMessage(this.tr("Drop file here"));
      newFileSection.add(fileDrop, {
        flex: 1
      });
      const newFilePView = new osparc.desktop.PanelView().set({
        title: this.tr("Select New File"),
        content: newFileSection
      });
      collapsibleViews.push(newFilePView);

      const downloadLinkSection = this.__getDownloadLinkSection();
      const downloadLinkPView = new osparc.desktop.PanelView().set({
        title: this.tr("Select Download Link"),
        content: downloadLinkSection
      });
      collapsibleViews.push(downloadLinkPView);

      const fileBrowserLayout = this.__getFileBrowserLayout();
      const usedFilePView = new osparc.desktop.PanelView().set({
        title: this.tr("Select File from other ") + osparc.product.Utils.getStudyAlias(),
        content: fileBrowserLayout
      });
      collapsibleViews.push(usedFilePView);

      const radioCollapsibleViews = new osparc.desktop.RadioCollapsibleViews();
      collapsibleViews.forEach(cv => {
        cv.getInnerContainer().set({
          margin: contentMargin
        });
        this._add(cv, {
          flex: 1
        });
        radioCollapsibleViews.addCollapsibleView(cv);
      });
      radioCollapsibleViews.openCollapsibleView(0);
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

    __resetOutput: function() {
      const node = this.getNode();
      osparc.file.FilePicker.resetOutputValue(node);
      this.fireEvent("itemReset");
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
    }
  }
});
