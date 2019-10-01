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
 *   let filePicker = new osparc.file.FilePicker(node, studyId);
 *   this.getRoot().add(filePicker);
 * </pre>
 */

qx.Class.define("osparc.file.FilePicker", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    * @param studyId {String} StudyId of the study that node belongs to
  */
  construct: function(node, studyId) {
    this.base(arguments);

    this.set({
      node,
      studyId
    });

    const filePickerLayout = new qx.ui.layout.VBox();
    this._setLayout(filePickerLayout);

    const reloadButton = this._createChildControlImpl("reloadButton");
    reloadButton.addListener("execute", function() {
      this.__filesTree.resetCache();
      this.__initResources();
    }, this);

    const filesTree = this.__filesTree = this._createChildControlImpl("filesTree");
    filesTree.addListener("selectionChanged", this.__selectionChanged, this);
    filesTree.addListener("itemSelected", this.__itemSelected, this);
    filesTree.addListener("filesAddedToTree", this.__filesAdded, this);

    const toolbar = new qx.ui.toolbar.ToolBar();
    const mainButtons = this.__mainButtons = new qx.ui.toolbar.Part();
    toolbar.addSpacer();
    toolbar.add(mainButtons);

    this._add(toolbar);

    const addBtn = this._createChildControlImpl("addButton");
    addBtn.addListener("fileAdded", e => {
      const fileMetadata = e.getData();
      if ("location" in fileMetadata && "path" in fileMetadata) {
        this.__setOutputFile(fileMetadata["location"], fileMetadata["path"], fileMetadata["name"]);
      }
      this.__initResources(fileMetadata["location"]);
    }, this);

    const selectBtn = this.__selectBtn = this._createChildControlImpl("selectButton");
    selectBtn.setEnabled(false);
    selectBtn.addListener("execute", function() {
      this.__itemSelected();
    }, this);

    this.__initResources();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
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
        case "addButton":
          control = new osparc.file.FilesAdd().set({
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
        this.__setOutputFile(selectedItem.getLocation(), selectedItem.getFileId(), selectedItem.getLabel());
        this.getNode().setProgress(100);
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    },

    __getOutputFile: function() {
      const outputs = this.getNode().getOutputs();
      return outputs["outFile"];
    },

    __setOutputFile: function(store, path, label) {
      if (store && path) {
        const outputs = this.__getOutputFile();
        outputs["value"] = {
          store,
          path,
          label
        };
      }
    },

    __filesAdded: function() {
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
