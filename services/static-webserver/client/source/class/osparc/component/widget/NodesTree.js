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
      hideRoot: true,
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
    getSortingValue: function(node) {
      if (node.isFilePicker()) {
        return osparc.utils.Services.getSorting("file");
      } else if (node.isParameter()) {
        return osparc.utils.Services.getSorting("parameter");
      } else if (node.isIterator()) {
        return osparc.utils.Services.getSorting("iterator");
      } else if (node.isProbe()) {
        return osparc.utils.Services.getSorting("probe");
      }
      return osparc.utils.Services.getSorting(node.getMetaData().type);
    },

    nodesToModel: function(nodes) {
      const children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        const nodeInTree = {
          label: node.getLabel(),
          children: [],
          sortingValue: this.self().getSortingValue(node),
          statusColor: null,
          id: node.getNodeId(),
          node
        };
        children.push(nodeInTree);
      }
      return children;
    }
  },

  members: {
    __currentNodeId: null,

    getCurrentNodeId: function() {
      return this.__currentNodeId;
    },

    setCurrentNodeId: function(nodeId) {
      this.__currentNodeId = nodeId;
    },

    _applyStudy: function() {
      this.populateTree();
    },

    populateTree: function() {
      const data = this.__getNodesModelData();
      const newModel = qx.data.marshal.Json.createModel(data, true);
      this.setModel(newModel);
      const study = this.getStudy();
      this.setDelegate(this._getDelegate(study));
      const nChildren = newModel.getChildren().length;
      this.setHeight(nChildren*21 + 12);
    },

    __getNodesModelData: function() {
      const study = this.getStudy();
      const nodes = study.getWorkbench().getNodes();
      const data = {
        label: "Study",
        children: this.self().nodesToModel(nodes),
        sortingValue: 0,
        id: study.getUuid()
      };
      return data;
    },

    _getDelegate: function(study) {
      return {
        createItem: () => {
          const nodeTreeItem = new osparc.component.widget.NodeTreeItem();
          nodeTreeItem.addListener("fullscreenNode", e => this.__openFullscreen(e.getData()));
          nodeTreeItem.addListener("renameNode", e => this._openItemRenamer(e.getData()));
          nodeTreeItem.addListener("infoNode", e => this.__openNodeInfo(e.getData()));
          nodeTreeItem.addListener("deleteNode", e => this.__deleteNode(e.getData()));
          return nodeTreeItem;
        },
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("label", "label", null, item, id);
          c.bindProperty("id", "id", null, item, id);
          c.bindProperty("study", "study", null, item, id);
          c.bindProperty("node", "node", null, item, id);
          const node = study.getWorkbench().getNode(item.getModel().getId());
          if (item.getModel().getId() === study.getUuid()) {
            item.getChildControl("delete-button").exclude();
          } else if (node) {
            node.addListener("keyChanged", () => this.populateTree(), this);
          }
        },
        configureItem: item => {
          item.addListener("tap", () => {
            this.__openItem(item.getModel().getId());
            this.nodeSelected(item.getModel().getId());
          }, this);
          // This is needed to keep the label flexible
          item.addListener("resize", e => item.setMaxWidth(100), this);
        },
        sorter: (itemA, itemB) => itemA.getSortingValue() - itemB.getSortingValue()
      };
    },

    __getNodeModel: function(model, nodeId) {
      if (model.getId() === nodeId) {
        return model;
      } else if (model.getChildren() !== null) {
        let node = null;
        let children = model.getChildren().toArray();
        for (let i = 0; node === null && i < children.length; i++) {
          node = this.__getNodeModel(children[i], nodeId);
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

    _openItemRenamer: function(nodeId) {
      if (nodeId === undefined && this.__getSelection()) {
        nodeId = this.__getSelection().getId();
      }
      if (nodeId) {
        const study = this.getStudy();
        const node = study.getWorkbench().getNode(nodeId);
        const oldLabel = nodeId === study.getUuid() ? study.getName() : node.getLabel();
        const treeItemRenamer = new osparc.component.widget.Renamer(oldLabel);
        treeItemRenamer.addListener("labelChanged", e => {
          const {
            newLabel
          } = e.getData();
          if (nodeId === study.getUuid() && osparc.data.Permissions.getInstance().canDo("study.update", true)) {
            study.setName(newLabel);
          } else if (node && osparc.data.Permissions.getInstance().canDo("study.node.rename", true)) {
            node.setLabel(newLabel);
          }
          treeItemRenamer.close();
        }, this);
        const bounds = this.getLayoutParent().getContentLocation();
        treeItemRenamer.moveTo(bounds.left + 100, bounds.top + 150);
        treeItemRenamer.open();
      }
    },

    __openNodeInfo: function(nodeId) {
      if (nodeId === undefined && this.__getSelection()) {
        nodeId = this.__getSelection().getId();
      }
      if (nodeId) {
        const study = this.getStudy();
        if (nodeId === study.getUuid()) {
          const studyDetails = new osparc.studycard.Large(study);
          const title = this.tr("Study Details");
          const width = 500;
          const height = 500;
          osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
        } else {
          const node = study.getWorkbench().getNode(nodeId);
          const serviceDetails = new osparc.servicecard.Large(node.getMetaData(), {
            nodeId,
            label: node.getLabel(),
            study
          });
          const title = this.tr("Service information");
          const width = 600;
          const height = 700;
          osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
        }
      }
    },

    __deleteNode: function(nodeId) {
      if (nodeId === undefined && this.__getSelection()) {
        nodeId = this.__getSelection().getId();
      }
      if (nodeId) {
        this.fireDataEvent("removeNode", nodeId);
      }
    },

    nodeSelected: function(nodeId) {
      const item = this.__getNodeModel(this.getModel(), nodeId);
      if (item) {
        this.openNodeAndParents(item);
        this.setSelection(new qx.data.Array([item]));
      }
    },

    __attachEventHandlers: function() {
      this.addListener("keypress", keyEvent => {
        switch (keyEvent.getKeyIdentifier()) {
          case "F2":
            this._openItemRenamer();
            break;
          case "I":
            this.__openNodeInfo();
            break;
          case "Delete":
            this.__deleteNode();
            break;
        }
      }, this);
    }
  }
});
