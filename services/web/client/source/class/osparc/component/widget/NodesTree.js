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
 *   let nodesTree = new osparc.component.widget.NodesTree();
 *   this.getRoot().add(nodesTree);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodesTree", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__toolBar = this._createChildControlImpl("toolbar");
    this.__tree = this._createChildControlImpl("tree");

    this.__attachEventHandlers();
  },

  events: {
    "slidesEdit": "qx.event.type.Event",
    "nodeSelected": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "exportNode": "qx.event.type.Data",
    "changeSelectedNode": "qx.event.type.Data"
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
    },

    areSlidesEnabled: function() {
      return new Promise((resolve, reject) => {
        osparc.utils.LibVersions.getPlatformName()
          .then(platformName => {
            if (["dev", "master"].includes(platformName)) {
              resolve(true);
            } else {
              resolve(false);
            }
          });
      });
    }
  },

  members: {
    __toolBar: null,
    __tree: null,
    __editSlidesBtn: null,
    __exportButton: null,
    __openButton: null,
    __deleteButton: null,
    __currentNodeId: null,
    __toolbarInitMinWidth: null,

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

    _applyStudy: function(study) {
      this.__populateToolbar();
      this.populateTree();
    },

    setCurrentNodeId: function(nodeId) {
      this.__currentNodeId = nodeId;
    },

    __getToolbarButtons: function(toolbar) {
      const toolBarChildren = toolbar.getChildren();
      return toolBarChildren.filter(toolBarChild => toolBarChild instanceof qx.ui.toolbar.Button);
    },

    __buildToolbar: function() {
      const iconSize = 14;
      const toolbar = this.__toolBar = new qx.ui.toolbar.ToolBar();

      const editBtn = this.__editSlidesBtn = new qx.ui.toolbar.Button(this.tr("Edit Guided mode"), "@FontAwesome5Solid/caret-square-right/"+iconSize).set({
        visibility: "excluded"
      });
      editBtn.addListener("execute", () => {
        this.fireEvent("slidesEdit");
      }, this);
      toolbar.add(editBtn);

      toolbar.addSpacer();

      if (osparc.data.Permissions.getInstance().canDo("study.node.export")) {
        const exportButton = this.__exportButton = new qx.ui.toolbar.Button(this.tr("Export"), "@FontAwesome5Solid/share/"+iconSize);
        exportButton.addListener("execute", () => {
          this.__exportDAG();
        }, this);
        osparc.utils.Utils.setIdToWidget(exportButton, "exportServicesBtn");
        toolbar.add(exportButton);
      }

      const openButton = this.__openButton = new qx.ui.toolbar.Button(this.tr("Open"), "@FontAwesome5Solid/edit/"+iconSize);
      openButton.addListener("execute", e => {
        const selectedItem = this.__getSelection();
        if (selectedItem) {
          const nodeId = selectedItem ? selectedItem.getNodeId() : this.getStudy().getUuid();
          this.__openItem(nodeId);
        }
      }, this);
      osparc.utils.Utils.setIdToWidget(openButton, "openServiceBtn");
      toolbar.add(openButton);

      const renameButton = new qx.ui.toolbar.Button(this.tr("Rename"), "@FontAwesome5Solid/i-cursor/"+iconSize);
      renameButton.addListener("execute", e => {
        this.__openItemRenamer();
      }, this);
      osparc.utils.Utils.setIdToWidget(renameButton, "renameServiceBtn");
      toolbar.add(renameButton);

      const deleteButton = this.__deleteButton = new qx.ui.toolbar.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/"+iconSize).set({
        enabled: false
      });
      deleteButton.addListener("execute", e => {
        const msg = this.tr("Are you sure you want to delete node?");
        const win = new osparc.ui.window.Confirmation(msg);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteNode();
          }
        });
      }, this);
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteServiceBtn");
      toolbar.add(deleteButton);

      const toolBarBtns = this.__getToolbarButtons(toolbar);
      let btnsWidth = 11;
      toolBarBtns.forEach(toolBarBtn => {
        const pad = 5;
        const spa = 10;
        const width = toolBarBtn.getSizeHint().width + pad + spa;
        btnsWidth += width;
      });
      this.__toolbarInitMinWidth = btnsWidth;

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

    __populateToolbar: function() {
      this.self().areSlidesEnabled()
        .then(areSlidesEnabled => {
          const study = this.getStudy();
          const isOwner = osparc.data.model.Study.isOwner(study);
          this.__editSlidesBtn.setVisibility(areSlidesEnabled && isOwner ? "visible" : "excluded");
        });
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
      let oldModel = this.__tree.getModel();
      if (JSON.stringify(newModel) !== JSON.stringify(oldModel)) {
        study.bind("name", newModel, "label");
        this.__tree.setModel(newModel);
        this.__tree.setDelegate({
          createItem: () => new osparc.component.widget.NodeTreeItem(),
          bindItem: (c, item, id) => {
            c.bindDefaultProperties(item, id);
            c.bindProperty("nodeId", "nodeId", null, item, id);
            const node = study.getWorkbench().getNode(item.getModel().getNodeId());
            if (node) {
              node.bind("label", item.getModel(), "label");
            }
            c.bindProperty("label", "label", null, item, id);
          },
          configureItem: item => {
            item.addListener("dbltap", () => {
              this.__openItem(item.getModel().getNodeId());
              this.__selectedItem(item);
            }, this);
            item.addListener("tap", () => {
              this.__selectedItem(item);
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
      let treeSelection = this.__tree.getSelection();
      if (treeSelection.length < 1) {
        return null;
      }
      let selectedItem = treeSelection.toArray()[0];
      return selectedItem;
    },

    __exportDAG: function() {
      const selectedItem = this.__getSelection();
      if (selectedItem) {
        if (selectedItem.getIsContainer()) {
          const nodeId = selectedItem.getNodeId();
          this.fireDataEvent("exportNode", nodeId);
        } else {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Only Groups can be exported."), "ERROR");
        }
      }
    },

    __openItem: function(nodeId) {
      if (nodeId) {
        this.fireDataEvent("nodeSelected", nodeId);
      }
    },

    __selectedItem: function(item) {
      const nodeId = item.getModel().getNodeId();
      this.fireDataEvent("changeSelectedNode", nodeId);
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
          const study = this.getStudy();
          if (nodeId === study.getUuid() && osparc.data.Permissions.getInstance().canDo("study.update", true)) {
            const params = {
              name: newLabel
            };
            study.updateStudy(params)
              .then(data => {
                selectedItem.setLabel(data.name);
              });
          } else if (osparc.data.Permissions.getInstance().canDo("study.node.rename", true)) {
            selectedItem.setLabel(newLabel);
            const node = study.getWorkbench().getNode(nodeId);
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

    __deleteNode: function() {
      const selectedItem = this.__getSelection();
      if (selectedItem === null) {
        return;
      }
      this.fireDataEvent("removeNode", selectedItem.getNodeId());
    },

    nodeSelected: function(nodeId) {
      const dataModel = this.__tree.getModel();
      const item = this.__getNodeInTree(dataModel, nodeId);
      if (item) {
        this.__tree.openNodeAndParents(item);
        this.__tree.setSelection(new qx.data.Array([item]));

        const studyId = this.getStudy().getUuid();
        if (this.__exportButton) {
          this.__exportButton.setEnabled(studyId !== nodeId && item.getIsContainer());
        }
        if (this.__deleteButton) {
          this.__deleteButton.setEnabled(studyId !== nodeId && this.__currentNodeId !== nodeId);
        }
        if (this.__openButton) {
          this.__openButton.setEnabled(this.__currentNodeId !== nodeId);
        }
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

      this.__toolBar.addListener("resize", () => {
        const toolBarBtns = this.__getToolbarButtons(this.__toolBar);
        if (this.__toolBar.getBounds().width < this.__toolbarInitMinWidth) {
          // Hide Label
          toolBarBtns.forEach(toolBarBtn => {
            const label = toolBarBtn.getChildControl("label");
            label.exclude();
            toolBarBtn.setToolTipText(label.getValue());
          });
        } else {
          // Show Label
          toolBarBtns.forEach(toolBarBtn => {
            toolBarBtn.getChildControl("label").show();
            toolBarBtn.setToolTipText(null);
          });
        }
      }, this);

      qx.event.message.Bus.getInstance().subscribe("updateStudy", () => {
        this.populateTree();
      }, this);
    }
  }
});
