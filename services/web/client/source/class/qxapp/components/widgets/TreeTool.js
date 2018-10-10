qx.Class.define("qxapp.components.widgets.TreeTool", {
  extend: qx.ui.core.Widget,

  construct: function(projectName, workbenchModel) {
    this.base(arguments);

    let treeLayout = new qx.ui.layout.VBox(10);
    this._setLayout(treeLayout);

    this.set({
      projectName: projectName,
      workbenchModel: workbenchModel
    });

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

    buildTree: function() {
      this.__buildLayout();

      const topLevelNodes = this.getWorkbenchModel().getNodeModels();

      let data = {
        label: this.getProjectName(),
        children: this.__convertModel(topLevelNodes),
        nodeId: "root"
      };
      var model = qx.data.marshal.Json.createModel(data, true);
      this.__tree.setModel(model);
    },

    __buildLayout: function() {
      let tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });

      this._removeAll();
      this._add(tree);

      this.__tree.addListener("dblclick", function(e) {
        let selection = this.__tree.getSelection();
        let currentSelection = selection.toArray();
        if (currentSelection.length > 0) {
          let selectedRow = currentSelection[0];
          this.fireDataEvent("NodeDoubleClicked", selectedRow.getNodeId());
        }
      }, this);
    },

    __convertModel: function(nodes) {
      let children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        let nodeInTree = {
          label: "",
          children: [],
          nodeId: node.getNodeId()
        };
        if (node.isContainer()) {
          nodeInTree.label = node.getName();
          nodeInTree.children = this.__convertModel(node.getInnerNodes());
        } else {
    getPath: function(nodeId) {
      let nodePath = "Workbench / ";
      if (nodeId) {
        let dataModel = this.__tree.getDataModel();
        for (let i=0; i<dataModel.getRowCount(); i++) {
          if (dataModel.getRowData(i)[1] === nodeId) {
            const node = dataModel.getData();
            const hierarchy = this.__tree.getHierarchy(node[i+1]).join(" / ");
            nodePath += hierarchy;
          }
        }
      }
      return nodePath;
    },

    __updateMe: function(value, old) {
      console.log("__updateMe");
    },

    __applyMe: function(value, old) {
      console.log("__applyMe");
    }
  }
});
