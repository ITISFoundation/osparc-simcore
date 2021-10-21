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
 * VirtualTree populated with NodeTreeItems
 *
 *   Helps the user navigating through nodes and gives a hierarchical view of containers. Also allows
 * some operations.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodesTree = new osparc.component.widget.NodesTree();
 *   this.getRoot().add(nodesTree);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodesTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      decorator: "service-tree",
      openMode: "none",
      contentPadding: 0,
      padding: 0
    });
    osparc.utils.Utils.setIdToWidget(this, "nodesTree");

    this.__attachEventHandlers();
  },

  events: {
    "nodeSelected": "qx.event.type.Data",
    "fullscreenNode": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false,
      apply: "_applyStudy"
    }
  },

  statics: {
    convertModel: function(nodes) {
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
          nodeInTree.children = this.convertModel(node.getInnerNodes());
        }
        children.push(nodeInTree);
      }
      return children;
    }
  },

  members: {
    __currentNodeId: null,

    _applyStudy: function() {
      this.populateTree();
    },

    getCurrentNodeId: function() {
      return this.__currentNodeId;
    },


    setCurrentNodeId: function(nodeId) {
      this.__currentNodeId = nodeId;
    },

    __getOneSelectedRow: function() {
      const selection = this.getSelection();
      if (selection && selection.toArray().length > 0) {
        return selection.toArray()[0];
      }
      return null;
    },

    populateTree: function() {
      const study = this.getStudy();
      const topLevelNodes = study.getWorkbench().getNodes();
      let data = {
        label: study.getName(),
        children: this.self().convertModel(topLevelNodes),
        nodeId: study.getUuid(),
        isContainer: true
      };
      let newModel = qx.data.marshal.Json.createModel(data, true);
      let oldModel = this.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        study.bind("name", newModel, "label");
        this.setModel(newModel);
        this.setDelegate({
          createItem: () => {
            const nodeTreeItem = new osparc.component.widget.NodeTreeItem();
            nodeTreeItem.addListener("fullscreenNode", e => this.__openFullscreen(e.getData()));
            nodeTreeItem.addListener("renameNode", e => this.__openItemRenamer(e.getData()));
            nodeTreeItem.addListener("showInfo", e => this.__openNodeInfo(e.getData()));
            nodeTreeItem.addListener("deleteNode", e => this.__deleteNode(e.getData()));
            return nodeTreeItem;
          },
          bindItem: (c, item, id) => {
            c.bindDefaultProperties(item, id);
            c.bindProperty("nodeId", "nodeId", null, item, id);
            const node = study.getWorkbench().getNode(item.getModel().getNodeId());
            if (node) {
              node.bind("label", item.getModel(), "label");
            }
            c.bindProperty("label", "label", null, item, id);
            if (item.getModel().getNodeId() === study.getUuid()) {
              item.setIcon("@FontAwesome5Solid/home/14");
              item.getChildControl("options-menu-button").exclude();
            }
            if (node) {
              if (node.isDynamic()) {
                item.getChildControl("fullscreen-button").show();
              }
              if (node.isFilePicker()) {
                const icon = osparc.utils.Services.getIcon("file");
                item.setIcon(icon+"14");
              } else if (node.isParameter()) {
                const icon = osparc.utils.Services.getIcon("parameter");
                item.setIcon(icon+"14");
              } else {
                const icon = osparc.utils.Services.getIcon(node.getMetaData().type);
                if (icon) {
                  item.setIcon(icon+"14");
                }
              }
            }
          },
          configureItem: item => {
            item.addListener("tap", () => {
              this.__openItem(item.getModel().getNodeId());
              this.nodeSelected(item.getModel().getNodeId());
            }, this);
          }
        });
      }
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
      let treeSelection = this.getSelection();
      if (treeSelection.length < 1) {
        return null;
      }
      let selectedItem = treeSelection.toArray()[0];
      return selectedItem;
    },

    __openItem: function(nodeId) {
      if (nodeId) {
        this.fireDataEvent("nodeSelected", nodeId);
      }
    },

    __openFullscreen: function(nodeId) {
      if (nodeId) {
        this.fireDataEvent("fullscreenNode", nodeId);
      }
    },

    __openItemRenamer: function(nodeId) {
      const renameItem = nodeId === undefined ? this.__getSelection() : this.__getNodeInTree(this.getModel(), nodeId);
      if (renameItem) {
        const treeItemRenamer = new osparc.component.widget.Renamer(renameItem.getLabel());
        treeItemRenamer.addListener("labelChanged", e => {
          const {
            newLabel
          } = e.getData();
          const selectedNodeId = renameItem.getNodeId();
          const study = this.getStudy();
          if (selectedNodeId === study.getUuid() && osparc.data.Permissions.getInstance().canDo("study.update", true)) {
            const params = {
              name: newLabel
            };
            study.updateStudy(params);
          } else if (osparc.data.Permissions.getInstance().canDo("study.node.rename", true)) {
            renameItem.setLabel(newLabel);
            const node = study.getWorkbench().getNode(selectedNodeId);
            if (node) {
              node.renameNode(newLabel);
            }
          }
          treeItemRenamer.close();
        }, this);
        const bounds = this.getLayoutParent().getContentLocation();
        treeItemRenamer.moveTo(bounds.left + 100, bounds.top + 150);
        treeItemRenamer.open();
      }
    },

    __openNodeInfo: function(nodeId) {
      if (nodeId) {
        const node = this.getStudy().getWorkbench().getNode(nodeId);
        const serviceDetails = new osparc.servicecard.Large(node.getMetaData());
        const title = this.tr("Service information");
        const width = 600;
        const height = 700;
        osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
      }
    },

    __deleteNode: function(nodeId) {
      if (nodeId === undefined) {
        const selectedItem = this.__getSelection();
        if (selectedItem === null) {
          return;
        }
        this.fireDataEvent("removeNode", selectedItem.getNodeId());
      } else {
        this.fireDataEvent("removeNode", nodeId);
      }
    },

    nodeSelected: function(nodeId) {
      const dataModel = this.getModel();
      const item = this.__getNodeInTree(dataModel, nodeId);
      if (item) {
        this.openNodeAndParents(item);
        this.setSelection(new qx.data.Array([item]));
      }
    },

    __attachEventHandlers: function() {
      this.addListener("keypress", keyEvent => {
        if (keyEvent.getKeyIdentifier() === "Delete") {
          this.__deleteNode();
        }
      }, this);

      this.addListener("keypress", keyEvent => {
        if (keyEvent.getKeyIdentifier() === "F2") {
          this.__openItemRenamer();
        }
      }, this);
    }
  }
});
