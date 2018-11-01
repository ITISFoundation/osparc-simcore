/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.component.widget.TreeTool", {
  extend: qx.ui.core.Widget,

  construct: function(projectName, workbenchModel) {
    this.base(arguments);

    let treeLayout = new qx.ui.layout.VBox(10);
    this._setLayout(treeLayout);

    this.set({
      projectName: projectName,
      workbenchModel: workbenchModel
    });

    this.__buildLayout();
    this.buildTree();

    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "F2") {
        this.__changeLabel();
      }
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data",
    "NodeLabelChanged": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false
    },

    projectName: {
      check: "String"
    }
  },

  members: {
    __tree: null,

    __buildLayout: function() {
      let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });

      this._removeAll();
      this._add(tree, {
        flex: 1
      });

      this.__tree.addListener("dblclick", e => {
        let selection = this.__tree.getSelection();
        let currentSelection = selection.toArray();
        if (currentSelection.length > 0) {
          let selectedRow = currentSelection[0];
          this.fireDataEvent("NodeDoubleClicked", selectedRow.getNodeId());
        }
      }, this);
    },

    buildTree: function() {
      const topLevelNodes = this.getWorkbenchModel().getNodeModels();
      let data = {
        label: this.getProjectName(),
        children: this.__convertModel(topLevelNodes),
        nodeId: "root",
        isContainer: true
      };
      let newModel = qx.data.marshal.Json.createModel(data, true);
      let oldModel = this.__tree.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        this.__tree.setModel(newModel);
        this.__tree.setDelegate({
          createItem: () => new qxapp.component.widget.NodeTreeItem(),
          bindItem: (c, item, id) => {
            c.bindDefaultProperties(item, id);
            c.bindProperty("label", "label", null, item, id);
            c.bindProperty("nodeId", "nodeId", null, item, id);
          }
        });
      }
    },

    __convertModel: function(nodes) {
      let children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        let nodeInTree = {
          label: "",
          nodeId: node.getNodeId()
        };
        nodeInTree.label = node.getLabel();
        nodeInTree.isContainer = node.isContainer();
        if (node.isContainer()) {
          nodeInTree.children = this.__convertModel(node.getInnerNodes());
        }
        children.push(nodeInTree);
      }
      return children;
    },

    __getNodeInTree: function(model, nodeId) {
      if (model.getNodeId() === nodeId) {
        return model;
      } else if (model.getIsContainer() && model.getChildren() !== null) {
        let node = null;
        let children = model.getChildren().toArray();
        for (let i=0; node === null && i < children.length; i++) {
          node = this.__getNodeInTree(children[i], nodeId);
        }
        return node;
      }
      return null;
    },

    nodeSelected: function(nodeId) {
      const dataModel = this.__tree.getModel();
      let nodeInTree = this.__getNodeInTree(dataModel, nodeId);
      if (nodeInTree) {
        this.__tree.openNodeAndParents(nodeInTree);
        this.__tree.setSelection(new qx.data.Array([nodeInTree]));
      }
    },

    __changeLabel: function() {
      let treeSelection = this.__tree.getSelection();
      if (treeSelection.length < 1) {
        return;
      }
      let selectedItem = treeSelection.toArray()[0];
      const selectedNodeId = selectedItem.getNodeId();
      if (selectedNodeId === "root") {
        return;
      }

      let nodeLabelEditor = this.__createNodeLabelEditor(selectedItem);
      const bounds = this.getLayoutParent().getBounds();
      nodeLabelEditor.moveTo(bounds.left+100, bounds.top+150);
      nodeLabelEditor.open();
    },

    __createNodeLabelEditor : function(selectedItem) {
      const oldLabel = selectedItem.getLabel();
      const maxWidth = 350;
      const minWidth = 100;
      const labelWidth = Math.min(Math.max(parseInt(oldLabel.length*4), minWidth), maxWidth);
      let labelEditorWin = new qx.ui.window.Window("Rename").set({
        appearance: "window-small-cap",
        layout: new qx.ui.layout.HBox(4),
        padding: 2,
        modal: true,
        showMaximize: false,
        showMinimize: false,
        width: labelWidth
      });

      // Create a text field in which to edit the data
      let labelEditor = new qx.ui.form.TextField(oldLabel).set({
        allowGrowX: true,
        minWidth: labelWidth
      });
      labelEditorWin.add(labelEditor, {
        flex: 1
      });

      labelEditorWin.addListener("appear", e => {
        labelEditor.focus();
        labelEditor.setTextSelection(0, labelEditor.getValue().length);
      }, this);

      // Create the "Save" button to close the cell editor
      let save = new qx.ui.form.Button("Save");
      save.addListener("execute", function(e) {
        const newLabel = labelEditor.getValue();
        selectedItem.setLabel(newLabel);
        const data = {
          nodeId: selectedItem.getNodeId(),
          newLabel: newLabel
        };
        this.fireDataEvent("NodeLabelChanged", data);

        labelEditorWin.close();
      }, this);
      labelEditorWin.add(save);

      // Let user press Enter from the cell editor text field to finish.
      let command = new qx.ui.command.Command("Enter");
      command.addListener("execute", e => {
        save.execute();
        command.dispose();
        command = null;
      });

      // Let user press Enter from the cell editor text field to finish.
      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        labelEditorWin.close();
        commandEsc.dispose();
        commandEsc = null;
      });

      return labelEditorWin;
    }
  }
});
