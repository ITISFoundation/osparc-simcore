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

    buildTree: function() {
      this.__buildLayout();
      this.__populateTree();
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
    },

    __populateTree: function() {
      let dataModel = this.__tree.getDataModel();

      const nodes = this.getWorkbenchModel().getNodes();
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        if (node.type === "container") {
          const label = node.getMetaData().name;
          let branch = dataModel.addBranch(null, label, true);
          dataModel.setColumnData(branch, 1, nodeId);
        } else {
          const label = node.getMetaData().name + " " + node.getMetaData().version;
          let leaf = dataModel.addLeaf(null, label);
          dataModel.setColumnData(leaf, 1, nodeId);
        }
      }

      dataModel.setData();

      this.__tree.addListener("dblclick", function(e) {
        let nodeClicked = e.getData();
        console.log(nodeClicked);
      }, this);
    },

    __updateMe: function(value, old) {
      console.log("__updateMe");
    },

    __applyMe: function(value, old) {
      console.log("__updateMe");
    }
  }
});
