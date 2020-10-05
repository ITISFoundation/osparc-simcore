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
 * When the selection is made "finished" event will be fired
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
    "finished": "qx.event.type.Event"
  },

  statics: {
    getOutputLabel: function(outputValue) {
      if ("outFile" in outputValue) {
        const outInfo = outputValue["outFile"];
        if ("label" in outInfo) {
          return outInfo.label;
        }
        const splitFilename = outInfo.path.split("/");
        return splitFilename[splitFilename.length-1];
      } else if ("outFiles" in outputValue) {
        const outInfos = outputValue["outFiles"];
        if (outInfos.length === 1) {
          const outInfo = outInfos[0];
          if ("label" in outInfo) {
            return outInfo.label;
          }
          const splitFilename = outInfo.path.split("/");
          return splitFilename[splitFilename.length-1];
        }
        return "(" + outInfos.length + ")";
      }
      return null;
    }
  },

  members: {
    __filesTree: null,
    __filesAdder: null,
    __selectBtn: null,
    __mainButtons: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "reloadButton":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/sync-alt/16",
            allowGrowX: false
          });
          this._add(control);
          break;
        case "filesTree":
          control = new osparc.file.FilesTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "filesAdd":
          control = new osparc.file.FilesAdd().set({
            node: this.getNode()
          });
          this.__mainButtons.add(control);
          break;
        case "selectButton":
          control = new qx.ui.toolbar.Button(this.tr("Select"));
          this.__mainButtons.add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    buildLayout: function() {
      this._setLayout(new qx.ui.layout.VBox(5));

      const reloadButton = this._createChildControlImpl("reloadButton");
      reloadButton.addListener("execute", function() {
        this.__filesTree.resetCache();
        this.__initResources();
      }, this);

      const filesTree = this.__filesTree = this._createChildControlImpl("filesTree");
      if (this.getNode().isFileSweeper()) {
        filesTree.set({
          selectionMode: "multi"
        });
      }
      filesTree.addListener("selectionChanged", this.__selectionChanged, this);
      filesTree.addListener("itemSelected", this.__itemSelected, this);
      filesTree.addListener("filesAddedToTree", this.__checkSelectedFileIsListed, this);

      const toolbar = new qx.ui.toolbar.ToolBar();
      const mainButtons = this.__mainButtons = new qx.ui.toolbar.Part();
      toolbar.addSpacer();
      toolbar.add(mainButtons);

      this._add(toolbar);

      const filesAdd = this.__filesAdder = this._createChildControlImpl("filesAdd");
      filesAdd.addListener("fileAdded", e => {
        const fileMetadata = e.getData();
        if ("location" in fileMetadata && "dataset" in fileMetadata && "path" in fileMetadata && "name" in fileMetadata) {
          this.__setOutputFile(fileMetadata["location"], fileMetadata["dataset"], fileMetadata["path"], fileMetadata["name"]);
        }
        this.__filesTree.resetCache();
        this.__initResources();
      }, this);

      const selectBtn = this.__selectBtn = this._createChildControlImpl("selectButton");
      selectBtn.setEnabled(false);
      selectBtn.addListener("execute", function() {
        this.__itemSelected();
      }, this);
    },

    init: function() {
      if (this.__isOutputFileSelected()) {
        const outFile = this.__getOutputFile();
        this.__filesTree.loadFilePath(outFile.value);
      } else if (this.__areOutputFilesSelected()) {
        const outFiles = this.getOutputFiles();
        this.__filesTree.loadFilePaths(outFiles.value);
      } else {
        this.__initResources();
      }
    },

    uploadPendingFiles: function(files) {
      if (files.length > 0) {
        if (files.length > 1) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only one file is accepted"), "ERROR");
        }
        this.__filesAdder.retrieveUrlAndUpload(files[0]);
      }
    },

    __initResources: function() {
      this.__filesTree.populateTree();
    },

    __selectionChanged: function() {
      const data = this.__filesTree.getSelectedFile();
      this.__selectBtn.setEnabled(data ? data["isFile"] : false);
    },

    __itemSelected: function() {
      if (this.getNode().isFilePicker()) {
        this.__itemSelectedOne();
      } else if (this.getNode().isFileSweeper()) {
        this.__itemSelectedMulti();
      }
    },

    __itemSelectedOne: function() {
      const data = this.__filesTree.getSelectedFile();
      if (data && data["isFile"]) {
        const selectedItem = data["selectedItem"];
        this.__setOutputFile(selectedItem.getLocation(), selectedItem.getDatasetId(), selectedItem.getFileId(), selectedItem.getLabel());
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    },

    __itemSelectedMulti: function() {
      const data = this.__filesTree.getSelectedFiles();
      if (data) {
        this.__resetOutputFiles();
        data.forEach(selectedEntry => {
          if (selectedEntry["isFile"]) {
            const selectedItem = selectedEntry["selectedItem"];
            this.__appendOutputFile(selectedItem.getLocation(), selectedItem.getDatasetId(), selectedItem.getFileId(), selectedItem.getLabel());
          }
        });
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    },

    __getOutputFile: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFile"];
    },

    getOutputFiles: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFiles"];
    },

    __setOutputFile: function(store, dataset, path, label) {
      if (store !== undefined && path) {
        const outputs = this.__getOutputFile();
        outputs["value"] = {
          store,
          dataset,
          path,
          label
        };
        this.getNode().getStatus().setProgress(100);
      }
    },

    __resetOutputFiles: function() {
      const outputs = this.getOutputFiles();
      outputs["value"] = [];
      this.getNode().getStatus().setProgress(0);
    },

    __appendOutputFile: function(store, dataset, path, label) {
      if (store !== undefined && path) {
        const outputs = this.getOutputFiles();
        outputs["value"].push({
          store,
          dataset,
          path,
          label
        });
        this.getNode().getStatus().setProgress(100);
      }
    },

    __isOutputFileSelected: function() {
      const outFile = this.__getOutputFile();
      if (outFile && "value" in outFile && "path" in outFile.value) {
        return true;
      }
      return false;
    },

    __areOutputFilesSelected: function() {
      const outFile = this.getOutputFiles();
      if (outFile && "value" in outFile && Array.isArray(outFile.value) && outFile.value.length && "path" in outFile.value[0]) {
        return true;
      }
      return false;
    },

    __checkSelectedFileIsListed: function() {
      if (this.__isOutputFileSelected()) {
        const outFile = this.__getOutputFile();
        this.__filesTree.setSelectedFile(outFile.value.path);
        this.__filesTree.fireEvent("selectionChanged");
      } else if (this.__areOutputFilesSelected()) {
        this.__filesTree.resetSelection();
        const outFiles = this.getOutputFiles();
        outFiles.value.forEach(outFile => {
          this.__filesTree.addSelectedFile(outFile.path);
        });
        this.__filesTree.fireEvent("selectionChanged");
      }
    }
  }
});
