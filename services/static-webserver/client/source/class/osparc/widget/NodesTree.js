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
 *   let nodesTree = new osparc.widget.NodesTree();
 *   this.getRoot().add(nodesTree);
 * </pre>
 */

qx.Class.define("osparc.widget.NodesTree", {
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
    "changeSelectedNode": "qx.event.type.Data",
    "fullscreenNode": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false,
      apply: "_applyStudy"
    },

    simpleNodes: {
      check: "Boolean",
      nullable: true,
      init: false,
      event: "changeSimpleNodes"
    }
  },

  statics: {
    __getSortingValue: function(node) {
      if (node.isFilePicker()) {
        return osparc.service.Utils.getSorting("file");
      } else if (node.isParameter()) {
        return osparc.service.Utils.getSorting("parameter");
      } else if (node.isIterator()) {
        return osparc.service.Utils.getSorting("iterator");
      } else if (node.isProbe()) {
        return osparc.service.Utils.getSorting("probe");
      }
      return osparc.service.Utils.getSorting(node.getMetaData().type);
    },

    __getIcon: function(node) {
      let icon = null;
      if (node.isFilePicker()) {
        icon = osparc.service.Utils.getIcon("file");
      } else if (node.isParameter()) {
        icon = osparc.service.Utils.getIcon("parameter");
      } else if (node.isIterator()) {
        icon = osparc.service.Utils.getIcon("iterator");
      } else if (node.isProbe()) {
        icon = osparc.service.Utils.getIcon("probe");
      } else {
        icon = osparc.service.Utils.getIcon(node.getMetaData().type);
      }
      if (icon) {
        icon += "14";
      }
      return icon;
    },

    createStudyModel: function(study) {
      const studyData = {
        id: study.getUuid(),
        label: osparc.product.Utils.getStudyAlias({firstUpperCase: true}),
        children: [],
        icon: "@FontAwesome5Solid/home/14",
        iconColor: "text",
        sortingValue: 0,
        study
      };
      const studyModel = qx.data.marshal.Json.createModel(studyData, true);
      study.bind("name", studyModel, "label");
      return studyModel;
    },

    nodeToModel: function(node) {
      const nodeData = {
        id: node.getNodeId(),
        label: "Node",
        children: [],
        icon: this.__getIcon(node),
        iconColor: "text",
        sortingValue: this.__getSortingValue(node),
        node
      };
      const nodeModel = qx.data.marshal.Json.createModel(nodeData, true);
      node.bind("label", nodeModel, "label");
      if (node.isDynamic()) {
        node.getStatus().bind("interactive", nodeModel, "iconColor", {
          converter: status => osparc.service.StatusUI.getColor(status)
        });
      } else if (node.isComputational()) {
        node.getStatus().bind("running", nodeModel, "iconColor", {
          converter: status => osparc.service.StatusUI.getColor(status)
        });
      }
      return nodeModel;
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
      const study = this.getStudy();
      const rootModel = this.self().createStudyModel(study);
      this.setModel(rootModel);
      const nodes = study.getWorkbench().getNodes();
      for (const nodeId in nodes) {
        const node = nodes[nodeId];
        const nodeInTree = this.self().nodeToModel(node);
        rootModel.getChildren().push(nodeInTree);
      }
      this.setDelegate(this._getDelegate(study));
      const nChildren = rootModel.getChildren().length;
      this.setHeight(nChildren*30 + 12);
    },

    _getDelegate: function(study) {
      return {
        createItem: () => {
          const nodeTreeItem = new osparc.widget.NodeTreeItem();
          this.bind("simpleNodes", nodeTreeItem, "simpleNode");
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
          c.bindProperty("icon", "icon", null, item, id);
          c.bindProperty("iconColor", "iconColor", null, item, id);
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
        this.fireDataEvent("changeSelectedNode", nodeId);
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
        const treeItemRenamer = new osparc.widget.Renamer(oldLabel);
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
        const width = osparc.info.CardLarge.WIDTH;
        const height = osparc.info.CardLarge.HEIGHT;
        if (nodeId === study.getUuid()) {
          const studyDetails = new osparc.info.StudyLarge(study);
          const title = this.tr("Study Information");
          osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height).set({
            maxHeight: height
          });
        } else {
          const node = study.getWorkbench().getNode(nodeId);
          const metadata = node.getMetaData();
          const serviceDetails = new osparc.info.ServiceLarge(metadata, {
            nodeId,
            label: node.getLabel(),
            studyId: study.getUuid()
          });
          osparc.info.ServiceLarge.popUpInWindow(serviceDetails);
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
