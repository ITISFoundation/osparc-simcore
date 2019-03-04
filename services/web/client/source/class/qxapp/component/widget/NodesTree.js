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
 * Widget that shows workbench hierarchy in tree view.
 *
 * It contains:
 * - Toolbar for adding, removing or renaming nodes
 * - VirtualTree populated with NodeTreeItems
 *
 *   Helps the user navigating through nodes and gives a hierarchical view of containers. Also allows
 * some operations.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodesTree = new qxapp.component.widget.NodesTree(project.getName(), project.getWorkbench());
 *   this.getRoot().add(nodesTree);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodesTree", {
  extend: qx.ui.core.Widget,

  /**
    * @param projectName {String} Project Name for displaying as root of the tree
    * @param workbench {qxapp.data.model.Workbench} Workbench owning the widget
  */
  construct: function(projectName, workbench) {
    this.base(arguments);

    this.set({
      projectName: projectName,
      workbench: workbench
    });

    this._setLayout(new qx.ui.layout.VBox());

    this.__toolBar = this._createChildControlImpl("toolbar");
    this.__tree = this._createChildControlImpl("tree");
    this.populateTree();

    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Delete") {
        this.__deleteNode();
      }
    }, this);
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "F2") {
        this.__renameNode();
      }
    }, this);
  },

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "addNode": "qx.event.type.Event",
    "removeNode": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
  },

  properties: {
    workbench: {
      check: "qxapp.data.model.Workbench",
      nullable: false
    },

    projectName: {
      check: "String"
    }
  },

  members: {
    __toolBar: null,
    __tree: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "toolbar":
          control = this.__buildToolbar();
          this._add(control);
          break;
        case "tree":
          control = this.__buildTree();
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildToolbar: function() {
      const iconSize = 16;
      let toolbar = this.__toolBar = new qx.ui.toolbar.ToolBar();

      let newButton = new qx.ui.toolbar.Button("New", "@FontAwesome5Solid/plus/"+iconSize);
      newButton.addListener("execute", e => {
        this.__addNode();
      }, this);
      toolbar.add(newButton);
      let part2 = new qx.ui.toolbar.Part();
      let deleteButton = new qx.ui.toolbar.Button("Delete", "@FontAwesome5Solid/trash/"+iconSize);
      deleteButton.addListener("execute", e => {
        this.__deleteNode();
      }, this);
      let renameButton = new qx.ui.toolbar.Button("Rename", "@FontAwesome5Solid/i-cursor/"+iconSize);
      renameButton.addListener("execute", e => {
        this.__renameNode();
      }, this);
      part2.add(deleteButton);
      part2.add(renameButton);
      toolbar.add(part2);

      return toolbar;
    },

    __getOneSelectedRow: function() {
      const selection = this.__tree.getSelection();
      if (selection && selection.toArray().length > 0) {
        return selection.toArray()[0];
      }
      return null;
    },

    __buildTree: function() {
      let tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });
      tree.addListener("dbltap", e => {
        const currentSelection = this.__getOneSelectedRow();
        if (currentSelection) {
          this.fireDataEvent("nodeDoubleClicked", currentSelection.getNodeId());
        }
      }, this);
      tree.addListener("tap", e => {
        const currentSelection = this.__getOneSelectedRow();
        if (currentSelection) {
          this.fireDataEvent("changeSelectedNode", currentSelection.getNodeId());
        }
      }, this);
      return tree;
    },

    populateTree: function() {
      const topLevelNodes = this.getWorkbench().getNodes();
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
        for (let i = 0; node === null && i < children.length; i++) {
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

    __addNode: function() {
      this.fireEvent("addNode");
    },

    __deleteNode: function() {
      let selectedItem = this.__getSelection();
      if (selectedItem === null) {
        return;
      }
      this.fireDataEvent("removeNode", selectedItem.getNodeId());
    },

    __renameNode: function() {
      let selectedItem = this.__getSelection();
      if (selectedItem === null) {
        return;
      }

      let treeItemRenamer = new qxapp.component.widget.TreeItemRenamer(selectedItem);
      treeItemRenamer.addListener("labelChanged", e => {
        const data = e.getData();
        const newLabel = data.newLabel;
        const nodeId = selectedItem.getNodeId();
        let node = this.getWorkbench().getNode(nodeId);
        node.setLabel(newLabel);
      }, this);
      const bounds = this.getLayoutParent().getBounds();
      treeItemRenamer.moveTo(bounds.left + 100, bounds.top + 150);
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
