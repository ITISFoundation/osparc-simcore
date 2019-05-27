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

    this.setNode(node);
    this.setStudyId(studyId);

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    let tree = this.__tree = this._createChildControlImpl("filesTree");
    tree.addListener("selectionChanged", this.__selectionChanged, this);
    tree.addListener("itemSelected", this.__itemSelected, this);
    tree.addListener("modelChanged", this.__modelChanged, this);

    let addBtn = this._createChildControlImpl("addButton");
    addBtn.addListener("fileAdded", e => {
      const data = e.getData();
      if ("location" in data && "path" in data) {
        this.__setOutputFile(data["location"], data["path"]);
      }
      this.__initResources();
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
    __tree: null,
    __selectBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filesTree":
          control = new qxapp.file.FilesTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "progressBox":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 1);
          break;
        case "addButton":
          control = new qxapp.file.FilesAdd().set({
            node: this.getNode(),
            studyId: this.getStudyId()
          });
          this._add(control);
          break;
        case "selectButton":
          control = new qx.ui.form.Button(this.tr("Select"));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __initResources: function() {
      this.__tree.populateTree();
    },

    __selectionChanged: function() {
      const data = this.__tree.getSelectedFile();
      this.__selectBtn.setEnabled(data ? data["isFile"] : false);
    },

    __itemSelected: function() {
      const data = this.__tree.getSelectedFile();
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
        this.__tree.setSelectedFile(outFile.value.path);
        this.__tree.fireEvent("selectionChanged");
      }
    }
  }
});
