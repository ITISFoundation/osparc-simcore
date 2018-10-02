qx.Class.define("qxapp.components.widgets.TreeTool", {
  extend: qx.ui.core.Widget,

  construct: function(workbenchModel) {
    this.base(arguments);

    let treeLayout = new qx.ui.layout.VBox(10);
    this._setLayout(treeLayout);

    this.setWorkbenchModel(workbenchModel);

    this.buildTree();
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  properties: {
    workbenchModel: {
      check: "qxapp.data.model.WorkbenchModel",
      nullable: false,
      event: "__updateMe",
      apply: "__applyMe"
    }
  },

  members: {
    __tree: null,
    __selectedNodeId: null,

    buildTree: function() {
      this.__buildLayout();

      const nodes = this.getWorkbenchModel().getNodes();
      this.__populateTree(nodes);
    },

    __buildLayout: function() {
      let tree = this.__tree = new qx.ui.treevirtual.TreeVirtual([
        "Tree",
        "NodeId",
        "Status"
      ]);
      tree.set({
        // alwaysShowOpenCloseSymbol: true,
        columnVisibilityButtonVisible: false,
        statusBarVisible: false
      });

      // Obtain the resize behavior object to manipulate
      let resizeBehavior = tree.getTableColumnModel().getBehavior();

      // Ensure that the tree column remains sufficiently wide
      resizeBehavior.set(0, {
        width: "1*",
        minWidth: 180
      });

      this._removeAll();
      this._add(tree);

      this.__tree.addListener("changeSelection", function(e) {
        let selectedRow = e.getData();
        this.__selectedNodeId = selectedRow[0].columnData[1];
      }, this);

      this.__tree.addListener("dblclick", function() {
        this.fireDataEvent("NodeDoubleClicked", this.__selectedNodeId);
      }, this);
    },

    __populateTree: function(nodes, parent = null) {
      let dataModel = this.__tree.getDataModel();

      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        if (node.isContainer()) {
          const label = node.getMetaData().name;
          let branch = dataModel.addBranch(parent, label, true);
          dataModel.setColumnData(branch, 1, nodeId);
          this.__populateTree(node.getInnerNodes(), branch);
        } else {
          const label = node.getMetaData().name + " " + node.getMetaData().version;
          let leaf = dataModel.addLeaf(parent, label);
          dataModel.setColumnData(leaf, 1, nodeId);
        }
      }

      dataModel.setData();
    },

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
