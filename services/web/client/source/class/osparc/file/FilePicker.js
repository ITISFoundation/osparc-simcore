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
  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.set({
      node
    });
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  statics: {
    getOutput: function(outputs) {
      if ("outFile" in outputs && "value" in outputs["outFile"]) {
        return outputs["outFile"]["value"];
      }
      return null;
    },

    getOutputLabel: function(outputs) {
      const outFileValue = this.getOutput(outputs);
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
      const outFileValue = this.getOutput(outputs);
      return (outFileValue && typeof outFileValue === "object" && "path" in outFileValue);
    },

    isOutputDownloadLink: function(outputs) {
      const outFileValue = this.getOutput(outputs);
      return (outFileValue && typeof outFileValue === "object" && "downloadLink" in outFileValue);
    },

    extractLabelFromLink: function(outputs) {
      const outFileValue = this.getOutput(outputs);
      return osparc.file.FileDownloadLink.extractLabelFromLink(outFileValue["downloadLink"]);
    },

    serializeOutput: function(outputs) {
      let output = {};
      const outFileValue = this.self().getOutput(outputs);
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
    __selectedFileLayout: null,
    __selectedFileFound: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "reload-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/sync-alt/16",
            allowGrowX: false
          });
          this._addAt(control, this.self().POS.RELOAD);
          break;
        case "tree-folder-layout":
          control = new qx.ui.splitpane.Pane("horizontal");
          control.getChildControl("splitter").set({
            width: 2,
            backgroundColor: "scrollbar-passive"
          });
          this._addAt(control, this.self().POS.FILES_TREE, {
            flex: 1
          });
          break;
        case "files-tree": {
          const treeFolderLayout = this.getChildControl("tree-folder-layout");
          control = new osparc.file.FilesTree().set({
            showLeafs: false,
            minWidth: 150,
            width: 200
          });
          treeFolderLayout.add(control, 0);
          break;
        }
        case "folder-viewer": {
          const treeFolderLayout = this.getChildControl("tree-folder-layout");
          control = new osparc.file.FolderViewer();
          treeFolderLayout.add(control, 1);
          break;
        }
        case "toolbar":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._addAt(control, this.self().POS.TOOLBAR);
          break;
        case "selected-file-layout": {
          control = new osparc.file.FileLabelWithActions().set({
            alignY: "middle"
          });
          const mainButtons = this.getChildControl("toolbar");
          mainButtons.add(control, {
            flex: 1
          });
          break;
        }
        case "files-add": {
          control = new osparc.file.FilesAdd().set({
            node: this.getNode()
          });
          const mainButtons = this.getChildControl("toolbar");
          mainButtons.add(control);
          break;
        }
        case "select-button": {
          control = new qx.ui.form.Button(this.tr("Select"));
          const mainButtons = this.getChildControl("toolbar");
          mainButtons.add(control);
          break;
        }
        case "file-download-link": {
          const groupBox = new qx.ui.groupbox.GroupBox(this.tr("Or provide a Download Link")).set({
            layout: new qx.ui.layout.VBox(5)
          });
          control = new osparc.file.FileDownloadLink();
          groupBox.add(control);
          this._addAt(groupBox, this.self().POS.DOWNLOAD_LINK);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __reloadFilesTree: function() {
      if (this.__filesTree) {
        this.__selectedFileFound = false;
        this.__filesTree.resetCache();
        this.__filesTree.populateTree();
      }
    },

    buildLayout: function() {
      const reloadButton = this.getChildControl("reload-button");
      reloadButton.addListener("execute", () => {
        this.__reloadFilesTree();
      }, this);

      const filesTree = this.__filesTree = this.getChildControl("files-tree");
      const folderViewer = this.__folderViewer = this.getChildControl("folder-viewer");

      filesTree.addListener("selectionChanged", () => {
        const selectionData = filesTree.getSelectedItem();
        this.__selectionChanged(selectionData);
        if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
          folderViewer.setFolder(selectionData);
        }
      }, this);
      filesTree.addListener("filesAddedToTree", () => {
        this.__checkSelectedFileIsListed();
      }, this);
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


      const selectedFileLayout = this.__selectedFileLayout = this.getChildControl("selected-file-layout");
      selectedFileLayout.getChildControl("delete-button").exclude();

      const filesAdd = this.getChildControl("files-add");
      filesAdd.addListener("fileAdded", e => {
        const fileMetadata = e.getData();
        if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
          this.__setOutputValueFromStore(fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
        }
        this.__reloadFilesTree();
        filesTree.loadFilePath(this.__getOutputFile()["value"]);
      }, this);

      const selectBtn = this.getChildControl("select-button");
      selectBtn.setEnabled(false);
      selectBtn.addListener("execute", () => {
        this.__itemSelected();
      }, this);

      const fileDownloadLink = this.getChildControl("file-download-link");
      fileDownloadLink.addListener("fileLinkAdded", e => {
        const downloadLink = e.getData();
        const label = osparc.file.FileDownloadLink.extractLabelFromLink(downloadLink);
        this.__setOutputValueFromLink(downloadLink, label);
      }, this);
    },

    init: function() {
      if (this.self().isOutputFromStore(this.getNode().getOutputs())) {
        const outFile = this.__getOutputFile();
        this.__filesTree.loadFilePath(outFile.value);
      }

      if (this.self().isOutputDownloadLink(this.getNode().getOutputs())) {
        const outFile = this.__getOutputFile();
        this.getChildControl("file-download-link").setValue(outFile.value["downloadLink"]);
      }
    },

    uploadPendingFiles: function(files) {
      if (files.length > 0) {
        if (files.length > 1) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
        this.getChildControl("files-add").retrieveUrlAndUpload(files[0]);
      }
    },

    __selectionChanged: function(selectedItem) {
      const isFile = osparc.file.FilesTree.isFile(selectedItem);
      this.getChildControl("select-button").setEnabled(isFile);

      this.__selectedFileLayout.itemSelected(selectedItem);
    },

    __itemSelected: function() {
      const selectedItem = this.__selectedFileLayout.getItemSelected();
      if (selectedItem && osparc.file.FilesTree.isFile(selectedItem)) {
        this.__setOutputValueFromStore(selectedItem.getLocation(), selectedItem.getDatasetId(), selectedItem.getFileId(), selectedItem.getLabel());
      }
    },

    __getOutputFile: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFile"];
    },

    __setOutputValueFromStore: function(store, dataset, path, label) {
      if (store !== undefined && path) {
        const outputs = this.getNode().getOutputs();
        outputs["outFile"]["value"] = {
          store,
          dataset,
          path,
          label
        };
        this.getNode().setOutputs({});
        this.getNode().setOutputs(outputs);
        this.getNode().getStatus().setProgress(100);
      }
    },

    __setOutputValueFromLink: function(downloadLink, label) {
      if (downloadLink) {
        const outputs = this.getNode().getOutputs();
        outputs["outFile"]["value"] = {
          downloadLink,
          label: label ? label : ""
        };
        this.getNode().setOutputs({});
        this.getNode().setOutputs(outputs);
        this.getNode().getStatus().setProgress(100);
      }
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
