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
 *   let nodesTree = new osparc.component.widget.NodesTree(study.getName(), study.getWorkbench());
 *   this.getRoot().add(nodesTree);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodesTree", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyName {String} Study Name for displaying as root of the tree
    * @param workbench {osparc.data.model.Workbench} Workbench owning the widget
  */
  construct: function(studyName, workbench) {
    this.base(arguments);

    this.set({
      studyName,
      workbench
    });

    this._setLayout(new qx.ui.layout.VBox());

    this.__toolBar = this._createChildControlImpl("toolbar");
    this.__tree = this._createChildControlImpl("tree");
    this.populateTree();

    this.__attachEventHandlers();
  },

  events: {
    "nodeDoubleClicked": "qx.event.type.Data",
    "addNode": "qx.event.type.Event",
    "removeNode": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
  },

  properties: {
    workbench: {
      check: "osparc.data.model.Workbench",
      nullable: false
    },

    studyName: {
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
      const iconSize = 14;
      const toolbar = this.__toolBar = new qx.ui.toolbar.ToolBar();

      const newButton = new qx.ui.toolbar.Button("New", "@FontAwesome5Solid/plus/"+iconSize, new qx.ui.command.Command("Ctrl+N"));
      newButton.addListener("execute", e => {
        this.__addNode();
      }, this);
      osparc.utils.Utils.setIdToWidget(newButton, "newServiceBtn");
      toolbar.add(newButton);

      toolbar.addSpacer();

      const openButton = new qx.ui.toolbar.Button("Open", "@FontAwesome5Solid/edit/"+iconSize);
      openButton.addListener("execute", e => {
        this.__openItem();
      }, this);
      osparc.utils.Utils.setIdToWidget(openButton, "openServiceBtn");
      toolbar.add(openButton);

      const renameButton = new qx.ui.toolbar.Button("Rename", "@FontAwesome5Solid/i-cursor/"+iconSize);
      renameButton.addListener("execute", e => {
        this.__openItemRenamer();
      }, this);
      osparc.utils.Utils.setIdToWidget(renameButton, "renameServiceBtn");
      toolbar.add(renameButton);

      const deleteButton = new qx.ui.toolbar.Button("Delete", "@FontAwesome5Solid/trash/"+iconSize);
      deleteButton.addListener("execute", e => {
        this.__deleteNode();
      }, this);
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteServiceBtn");
      toolbar.add(deleteButton);

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
      const tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        decorator: "service-tree",
        openMode: "none",
        contentPadding: 0,
        padding: 0
      });
      osparc.utils.Utils.setIdToWidget(tree, "nodesTree");
      return tree;
    },

    populateTree: function() {
      const topLevelNodes = this.getWorkbench().getNodes();
      let data = {
        label: this.getStudyName(),
        children: this.__convertModel(topLevelNodes),
        nodeId: "root",
        isContainer: true
      };
      let newModel = qx.data.marshal.Json.createModel(data, true);
      let oldModel = this.__tree.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        this.__tree.setModel(newModel);
        this.__tree.setDelegate({
          createItem: () => new osparc.component.widget.NodeTreeItem(),
          bindItem: (c, item, id) => {
            c.bindDefaultProperties(item, id);
            c.bindProperty("label", "label", null, item, id);
            c.bindProperty("nodeId", "nodeId", null, item, id);
          },
          configureItem: item => {
            item.addListener("dbltap", () => {
              this.__openItem(item.getModel().getNodeId());
            }, this);
            item.addListener("tap", e => {
              this.fireDataEvent("changeSelectedNode", item.getModel().getNodeId());
            }, this);
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
      return selectedItem;
    },

    __addNode: function() {
      this.fireEvent("addNode");
    },

    __deleteNode: function() {
      const selectedItem = this.__getSelection();
      if (selectedItem === null) {
        return;
      }
      this.fireDataEvent("removeNode", selectedItem.getNodeId());
    },

    __openItem: function(nodeId) {
      if (nodeId) {
        this.fireDataEvent("nodeDoubleClicked", nodeId);
      } else {
        const selectedItem = this.__getSelection();
        if (selectedItem === null) {
          this.fireDataEvent("nodeDoubleClicked", "root");
        } else {
          this.fireDataEvent("nodeDoubleClicked", selectedItem.getNodeId());
        }
      }
    },

    __openItemRenamer: function() {
      const selectedItem = this.__getSelection();
      if (selectedItem) {
        const treeItemRenamer = new osparc.component.widget.Renamer(selectedItem.getLabel());
        treeItemRenamer.addListener("labelChanged", e => {
          const {
            newLabel
          } = e.getData();
          const nodeId = selectedItem.getNodeId();
          if (nodeId === "root") {
            const params = {
              name: newLabel
            };
            this.getWorkbench().getStudy()
              .updateStudy(params)
              .then(data => {
                selectedItem.setLabel(data.name);
              });
          } else {
            selectedItem.setLabel(newLabel);
            const node = this.getWorkbench().getNode(nodeId);
            if (node) {
              node.renameNode(newLabel);
            }
          }
        }, this);
        const bounds = this.getLayoutParent().getContentLocation();
        treeItemRenamer.moveTo(bounds.left + 100, bounds.top + 150);
        treeItemRenamer.open();
      }
    },

    nodeSelected: function(nodeId, openNodeAndParents = false) {
      const dataModel = this.__tree.getModel();
      const nodeInTree = this.__getNodeInTree(dataModel, nodeId);
      if (nodeInTree) {
        if (openNodeAndParents) {
          this.__tree.openNodeAndParents(nodeInTree);
        }
        this.__tree.setSelection(new qx.data.Array([nodeInTree]));
      }
    },

    __attachEventHandlers: function() {
      this.addListener("keypress", function(keyEvent) {
        if (keyEvent.getKeyIdentifier() === "Delete") {
          this.__deleteNode();
        }
      }, this);
      this.addListener("keypress", function(keyEvent) {
        if (keyEvent.getKeyIdentifier() === "F2") {
          this.__openItemRenamer();
        }
      }, this);
      qx.event.message.Bus.getInstance().subscribe("updateStudy", msg => {
        const {
          name
        } = msg.getData();
        this.setStudyName(name);
        if (this.isPropertyInitialized("workbench")) {
          this.populateTree();
        }
      }, this);
    }
  }
});
