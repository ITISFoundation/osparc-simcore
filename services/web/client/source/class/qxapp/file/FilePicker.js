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
 * Built-in service used for selecting a single file from storage and make it available in the workflow
 *
 *   It consists of a VBox containing a FilesTree, Add button and Select button:
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
 *   let filePicker = new qxapp.file.FilePicker(node, studyId);
 *   this.getRoot().add(filePicker);
 * </pre>
 */

qx.Class.define("qxapp.file.FilePicker", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param studyId {String} StudyId of the study that node belongs to
  */
  construct: function(node, studyId) {
    this.base(arguments);

    this.set({
      node,
      studyId
    });

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    let filesTree = this.__filesTree = this._createChildControlImpl("filesTree");
    filesTree.addListener("selectionChanged", this.__selectionChanged, this);
    filesTree.addListener("itemSelected", this.__itemSelected, this);
    filesTree.addListener("modelChanged", this.__modelChanged, this);

    const toolbar = new qx.ui.toolbar.ToolBar();
    const mainButtons = this.__mainButtons = new qx.ui.toolbar.Part();
    toolbar.addSpacer();
    toolbar.add(mainButtons);

    this._add(toolbar);

    let addBtn = this._createChildControlImpl("addButton");
    addBtn.addListener("fileAdded", e => {
      const fileMetadata = e.getData();
      if ("location" in fileMetadata && "path" in fileMetadata) {
        this.__setOutputFile(fileMetadata["location"], fileMetadata["path"]);
      }
      this.__initResources(fileMetadata["location"]);
    }, this);

    let selectBtn = this.__selectBtn = this._createChildControlImpl("selectButton");
    selectBtn.setEnabled(false);
    selectBtn.addListener("execute", function() {
      this.__itemSelected();
    }, this);

    this.__initResources();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node"
    },

    studyId: {
      check: "String",
      init: ""
    }
  },

  events: {
    "finished": "qx.event.type.Event"
  },

  members: {
    __filesTree: null,
    __selectBtn: null,
    __mainButtons: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filesTree":
          control = new qxapp.file.FilesTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "addButton":
          control = new qxapp.file.FilesAdd().set({
            node: this.getNode(),
            studyId: this.getStudyId()
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

    __initResources: function(locationId = null) {
      this.__filesTree.populateTree(null, locationId);
    },

    __selectionChanged: function() {
      const data = this.__filesTree.getSelectedFile();
      this.__selectBtn.setEnabled(data ? data["isFile"] : false);
    },

    __itemSelected: function() {
      const data = this.__filesTree.getSelectedFile();
      if (data && data["isFile"]) {
        const selectedItem = data["selectedItem"];
        const outputFile = this.__getOutputFile();
        outputFile.value = {
          store: selectedItem.getLocation(),
          path: selectedItem.getFileId()
        };
        this.getNode().setProgress(100);
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    },

    __getOutputFile: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFile"];
    },

    __setOutputFile: function(store, path) {
      if (store && path) {
        const outputs = this.getNode().getOutputs();
        outputs["value"]["outFile"] = {
          store,
          path
        };
      }
    },

    __modelChanged: function() {
      this.__checkSelectedFileIsListed();
    },

    __checkSelectedFileIsListed: function() {
      const outFile = this.__getOutputFile();
      if (outFile && "value" in outFile && "path" in outFile.value) {
        this.__filesTree.setSelectedFile(outFile.value.path);
        this.__filesTree.fireEvent("selectionChanged");
      }
    }
  }
});
