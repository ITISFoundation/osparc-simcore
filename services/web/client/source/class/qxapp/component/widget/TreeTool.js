qx.Class.define("qxapp.component.widget.TreeTool", {
  extend: qx.ui.core.Widget,

  construct: function(projectName, workbenchModel) {
    this.base(arguments);

    this.set({
      projectName: projectName,
      workbenchModel: workbenchModel
    });

    this._setLayout(new qx.ui.layout.VBox());

    this.__tree = this._createChildControlImpl("tree");
    this.populateTree();

    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "F2") {
        this.__renameItem();
      }
    }, this);
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tree":
          control = this.__buildTree();
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildTree: function() {
      let tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });
      tree.addListener("dbltap", e => {
        let selection = this.__tree.getSelection();
        let currentSelection = selection.toArray();
        if (currentSelection.length > 0) {
          let selectedRow = currentSelection[0];
          this.fireDataEvent("NodeDoubleClicked", selectedRow.getNodeId());
        }
      }, this);
      return tree;
    },

    populateTree: function() {
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

    __getSelection: function() {
      let treeSelection = this.__tree.getSelection();
      if (treeSelection.length < 1) {
        return null;
      }

      let selectedItem = treeSelection.toArray()[0];
      const selectedNodeId = selectedItem.getNodeId();
      if (selectedNodeId === "root") {
        return null;
      }

      return selectedItem;
    },

    __renameItem: function() {
      let selectedItem = this.__getSelection();
      if (selectedItem === null) {
        return;
      }

      let treeItemRenamer = new qxapp.component.widget.TreeItemRenamer(selectedItem);
      treeItemRenamer.addListener("LabelChanged", e => {
        const data = e.getData();
        const newLabel = data.newLabel;
        const nodeId = selectedItem.getNodeId();
        let nodeModel = this.getWorkbenchModel().getNodeModel(nodeId);
        nodeModel.setLabel(newLabel);
      }, this);
      const bounds = this.getLayoutParent().getBounds();
      treeItemRenamer.moveTo(bounds.left+100, bounds.top+150);
      treeItemRenamer.open();
    },

    nodeSelected: function(nodeId) {
      const dataModel = this.__tree.getModel();
      let nodeInTree = this.__getNodeInTree(dataModel, nodeId);
      if (nodeInTree) {
        this.__tree.openNodeAndParents(nodeInTree);
        this.__tree.setSelection(new qx.data.Array([nodeInTree]));
      }
    }
  }
});
