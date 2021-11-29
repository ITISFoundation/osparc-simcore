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

  events: {
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
      const outputs = node.getOutputs();
      outputs["outFile"]["value"] = outputValue;
      node.setOutputs({});
      node.setOutputs(outputs);
      node.getStatus().setHasOutputs(true);
      node.getStatus().setModified(false);
      const outLabel = osparc.file.FilePicker.getOutputLabel(outputs);
      if (outLabel) {
        node.setLabel(outputValue.label);
      }
      node.getStatus().setProgress(100);
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

    buildFileFromStoreInfoView: function(node, form) {
      const outValue = osparc.file.FilePicker.getOutput(node.getOutputs());
      const params = {
        url: {
          locationId: outValue.store,
          datasetId: outValue.dataset
        }
      };
      osparc.data.Resources.fetch("storageFiles", "getByLocationAndDataset", params)
        .then(files => {
          const fileMetadata = files.find(file => file.file_uuid === outValue.path);
          if (fileMetadata) {
            for (let [key, value] of Object.entries(fileMetadata)) {
              const entry = new qx.ui.form.TextField();
              form.add(entry, key, null, key);
              if (value) {
                entry.setValue(value.toString());
              }
            }
          }
        });
    },

    buildDownloadLinkInfoView: function(node, form) {
      const outputs = node.getOutputs();

      const outFileValue = osparc.file.FilePicker.getOutput(outputs);
      const urlEntry = new qx.ui.form.TextField().set({
        value: outFileValue
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

    buildInfoView: function(node) {
      const form = new qx.ui.form.Form();
      if (osparc.file.FilePicker.isOutputFromStore(node.getOutputs())) {
        this.self().buildFileFromStoreInfoView(node, form);
      } else if (osparc.file.FilePicker.isOutputDownloadLink(node.getOutputs())) {
        this.self().buildDownloadLinkInfoView(node, form);
      }

      return new qx.ui.form.renderer.Single(form);
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
            backgroundColor: "background-main-lighter+",
            showLeafs: false,
            minWidth: 150,
            width: 250
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
        case "select-toolbar":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            backgroundColor: "background-main-lighter+"
          });
          this._addAt(control, this.self().POS.TOOLBAR);
          break;
        case "files-add": {
          control = new osparc.file.FilesAdd().set({
            node: this.getNode()
          });
          const mainButtons = this.getChildControl("select-toolbar");
          mainButtons.add(control);
          break;
        }
        case "selected-file-layout": {
          control = new osparc.file.FileLabelWithActions().set({
            alignY: "middle"
          });
          const mainButtons = this.getChildControl("select-toolbar");
          mainButtons.add(control, {
            flex: 1
          });
          break;
        }
        case "select-button": {
          control = new qx.ui.form.Button(this.tr("Select"));
          const mainButtons = this.getChildControl("select-toolbar");
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


      const filesAdd = this.getChildControl("files-add");
      filesAdd.addListener("fileAdded", e => {
        const fileMetadata = e.getData();
        if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
          this.setOutputValueFromStore(fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
        }
        this.__reloadFilesTree();
        filesTree.loadFilePath(this.__getOutputFile()["value"]);
      }, this);

      const selectedFileLayout = this.__selectedFileLayout = this.getChildControl("selected-file-layout");
      selectedFileLayout.getChildControl("delete-button").exclude();

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
        if (files.length === 1) {
          this.getChildControl("files-add").retrieveUrlAndUpload(files[0]);
          return true;
        }
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
      }
      return false;
    },

    __selectionChanged: function(selectedItem) {
      const isFile = osparc.file.FilesTree.isFile(selectedItem);
      this.getChildControl("select-button").setEnabled(isFile);

      this.__selectedFileLayout.itemSelected(selectedItem);
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
    }
  }
});
