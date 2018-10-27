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
    __selectedNodeId: null,

    __buildLayout: function() {
      let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });

      this._removeAll();
      this._add(tree, {
        flex: 1
      });

      this.__tree.addListener("dbltap", e => {
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
    }
  }
});
