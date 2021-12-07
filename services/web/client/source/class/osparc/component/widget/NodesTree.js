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
    getSortingValue: function(node) {
      if (node.isFilePicker()) {
        return osparc.utils.Services.getSorting("file");
      } else if (node.isParameter()) {
        return osparc.utils.Services.getSorting("parameter");
      }
      return osparc.utils.Services.getSorting(node.getMetaData().type);
    },

    convertModel: function(nodes) {
      const children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        const nodeInTree = {
          label: node.getLabel(),
          children: node.isContainer() ? this.convertModel(node.getInnerNodes()) : [],
          isContainer: node.isContainer(),
          nodeId: node.getNodeId(),
          sortingValue: this.self().getSortingValue(node),
          statusColor: null
        };
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
      const data = this.__getModelData();
      let newModel = qx.data.marshal.Json.createModel(data, true);
      let oldModel = this.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        const study = this.getStudy();
        study.bind("name", newModel, "label");
        this.setModel(newModel);
        this.setDelegate({
          createItem: () => {
            const nodeTreeItem = new osparc.component.widget.NodeTreeItem();
            nodeTreeItem.addListener("fullscreenNode", e => this.__openFullscreen(e.getData()));
            nodeTreeItem.addListener("renameNode", e => this.__openItemRenamer(e.getData()));
            nodeTreeItem.addListener("infoNode", e => this.__openNodeInfo(e.getData()));
            nodeTreeItem.addListener("deleteNode", e => this.__deleteNode(e.getData()));
            return nodeTreeItem;
          },
          bindItem: (c, item, id) => {
            c.bindDefaultProperties(item, id);
            c.bindProperty("nodeId", "nodeId", null, item, id);
            c.bindProperty("label", "label", null, item, id);
            const node = study.getWorkbench().getNode(item.getModel().getNodeId());
            if (item.getModel().getNodeId() === study.getUuid()) {
              item.setIcon("@FontAwesome5Solid/home/14");
              item.getChildControl("options-delete-button").exclude();
            } else if (node) {
              node.bind("label", item.getModel(), "label");

              // set icon
              if (node.isFilePicker()) {
                const icon = osparc.utils.Services.getIcon("file");
                item.setIcon(icon+"14");
              } else if (node.isParameter()) {
                const icon = osparc.utils.Services.getIcon("parameter");
                item.setIcon(icon+"14");
              } else if (node.isIterator()) {
                const icon = osparc.utils.Services.getIcon("iterator");
                item.setIcon(icon+"14");
              } else if (node.isProbe()) {
                const icon = osparc.utils.Services.getIcon("iterator-consumer");
                item.setIcon(icon+"14");
              } else {
                const icon = osparc.utils.Services.getIcon(node.getMetaData().type);
                if (icon) {
                  item.setIcon(icon+"14");
                }
              }

              // "bind" running/interactive status to icon color
              if (node.isDynamic()) {
                node.getStatus().addListener("changeInteractive", e => this.__updateColor(node.getNodeId(), e.getData()));
                this.__updateColor(node.getNodeId(), node.getStatus().getInteractive());
              } else if (node.isComputational()) {
                node.getStatus().addListener("changeRunning", e => this.__updateColor(node.getNodeId(), e.getData()));
                this.__updateColor(node.getNodeId(), node.getStatus().getRunning());
              }
              c.bindProperty("statusColor", "textColor", {
                converter: statusColor => osparc.utils.StatusUI.getColor(statusColor)
              }, item.getChildControl("icon"), id);

              // add fullscreen
              if (node.isDynamic()) {
                item.getChildControl("fullscreen-button").show();
              }
            }
          },
          configureItem: item => {
            item.addListener("tap", () => {
              this.__openItem(item.getModel().getNodeId());
              this.nodeSelected(item.getModel().getNodeId());
            }, this);
            // This is needed to keep the label flexible
            item.addListener("resize", e => item.setMaxWidth(100), this);
          },
          sorter: (itemA, itemB) => itemA.getSortingValue() - itemB.getSortingValue()
        });
        const nChildren = newModel.getChildren().length;
        this.setHeight(nChildren*21 + 12);
      }
    },

    __getModelData: function() {
      const study = this.getStudy();
      const topLevelNodes = study.getWorkbench().getNodes();
      const data = this.__getRootModelData();
      data.children = this.self().convertModel(topLevelNodes);
      return data;
    },

    __getRootModelData: function() {
      const study = this.getStudy();
      const data = {
        label: study.getName(),
        children: [],
        isContainer: true,
        nodeId: study.getUuid(),
        sortingValue: 0
      };
      return data;
    },

    __updateColor: function(nodeId, status) {
      const nodeInTree = this.__getNodeModel(this.getModel(), nodeId);
      if (nodeInTree) {
        nodeInTree.setStatusColor(status);
      }
    },

    __getNodeModel: function(model, nodeId) {
      if (model.getNodeId() === nodeId) {
        return model;
      } else if (model.getIsContainer() && model.getChildren() !== null) {
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

    __openItemRenamer: function(nodeId) {
      if (nodeId === undefined && this.__getSelection()) {
        nodeId = this.__getSelection().getNodeId();
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
        nodeId = this.__getSelection().getNodeId();
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
          const serviceDetails = new osparc.servicecard.Large(node.getMetaData());
          const title = this.tr("Service information");
          const width = 600;
          const height = 700;
          osparc.ui.window.Window.popUpInWindow(serviceDetails, title, width, height);
        }
      }
    },

    __deleteNode: function(nodeId) {
      if (nodeId === undefined && this.__getSelection()) {
        nodeId = this.__getSelection().getNodeId();
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
            this.__openItemRenamer();
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
