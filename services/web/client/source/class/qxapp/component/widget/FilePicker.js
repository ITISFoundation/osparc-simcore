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

qx.Class.define("qxapp.component.widget.FilePicker", {
  extend: qx.ui.core.Widget,

  construct: function(node, projectId) {
    this.base(arguments);

    this.setNode(node);
    this.setProjectId(projectId);

    let filePickerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(filePickerLayout);

    let tree = this.__tree = this._createChildControlImpl("filesTree");
    tree.addListener("selectionChanged", this.__selectionChanged, this);
    tree.addListener("itemSelected", this.__itemSelected, this);

    let addBtn = this._createChildControlImpl("addButton");
    addBtn.addListener("fileAdded", e => {
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

    projectId: {
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
          control = new qxapp.component.widget.FilesTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "progressBox":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._addAt(control, 1);
          break;
        case "addButton":
          control = new qxapp.component.widget.FilesAdd(this.tr("Add file(s)")).set({
            node: this.getNode(),
            projectId: this.getProjectId()
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
      let data = this.__tree.getSelectedFile();
      if (data && data["isFile"]) {
        let selectedItem = data["selectedItem"];
        let outputs = this.getNode().getOutputs();
        outputs["outFile"].value = {
          store: selectedItem.getLocation(),
          path: selectedItem.getFileId()
        };
        this.getNode().repopulateOutputPortData();
        this.fireEvent("finished");
      }
    }
  }
});
