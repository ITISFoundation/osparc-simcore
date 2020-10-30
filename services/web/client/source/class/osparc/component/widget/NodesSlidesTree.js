/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.widget.NodesSlidesTree", {
  extend: qx.ui.core.Widget,

  construct: function(initData = {}) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__tree = this._createChildControlImpl("tree");
    const disable = this._createChildControlImpl("disable");
    disable.addListener("execute", () => this.__disableSlides(), this);
    const enable = this._createChildControlImpl("enable");
    enable.addListener("execute", () => this.__enableSlides(), this);

    const model = this.__initTree();
    this.__tree.setModel(model);

    this.__populateTree();
    this.__recalculatePositions();

    this.__initData(initData);
  },

  events: {
    "finished": "qx.event.type.Event"
  },

  statics: {
    convertModel: function(nodes) {
      let children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        let nodeInTree = {
          label: "",
          nodeId: node.getNodeId(),
          skipNode: false,
          position: -1
        };
        nodeInTree.label = node.getLabel();
        if (node.isContainer()) {
          nodeInTree.children = this.convertModel(node.getInnerNodes());
        }
        children.push(nodeInTree);
      }
      return children;
    },

    getItemsInTree: function(itemMdl, children = []) {
      children.push(itemMdl);
      for (let i=0; itemMdl.getChildren && i<itemMdl.getChildren().length; i++) {
        this.self().getItemsInTree(itemMdl.getChildren().toArray()[i], children);
      }
    },

    moveElement: function(input, from, to) {
      let numberOfDeletedElm = 1;
      const elm = input.splice(from, numberOfDeletedElm)[0];
      numberOfDeletedElm = 0;
      input.splice(to, numberOfDeletedElm, elm);
    }
  },

  members: {
    __tree: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tree":
          control = this.__buildTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "buttons":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "disable": {
          control = new qx.ui.form.Button(this.tr("Disable")).set({
            allowGrowX: false,
            appearance: "no-shadow-button"
          });
          const buttons = this.getChildControl("buttons");
          buttons.add(control);
          break;
        }
        case "enable": {
          control = new qx.ui.form.Button(this.tr("Enable")).set({
            allowGrowX: false,
            appearance: "no-shadow-button"
          });
          const buttons = this.getChildControl("buttons");
          buttons.add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __buildTree: function() {
      const tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        decorator: "service-tree",
        openMode: "none",
        contentPadding: 0,
        padding: 0,
        backgroundColor: "material-button-background"
      });
      return tree;
    },

    __initTree: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const topLevelNodes = study.getWorkbench().getNodes();
      let rootData = {
        label: study.getName(),
        children: this.self().convertModel(topLevelNodes),
        nodeId: study.getUuid(),
        skipNode: null,
        position: null
      };
      return qx.data.marshal.Json.createModel(rootData, true);
    },

    __populateTree: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();

      this.__tree.setDelegate({
        createItem: () => {
          const nodeSlideTreeItem = new osparc.component.widget.NodeSlideTreeItem();
          nodeSlideTreeItem.set({
            skipNode: false
          });
          return nodeSlideTreeItem;
        },
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("nodeId", "nodeId", null, item, id);
          const node = study.getWorkbench().getNode(item.getModel().getNodeId());
          if (node) {
            node.bind("label", item.getModel(), "label");
          }
          c.bindProperty("label", "label", null, item, id);
          c.bindProperty("position", "position", null, item, id);
          c.bindProperty("skipNode", "skipNode", null, item, id);
        },
        configureItem: item => {
          item.addListener("showNode", () => {
            this.__show(item.getModel());
            this.__recalculatePositions();
          }, this);
          item.addListener("hideNode", () => {
            this.__hide(item.getModel());
            this.__recalculatePositions();
          }, this);
          item.addListener("moveUp", () => {
            this.__moveUp(item.getModel());
            this.__recalculatePositions();
          }, this);
          item.addListener("moveDown", () => {
            this.__moveDown(item.getModel());
            this.__recalculatePositions();
          }, this);
        }
      });
    },

    __initData: function(initData) {
      if (Object.keys(initData).length) {
        const children = this.__tree.getModel().getChildren().toArray();
        children.forEach(child => {
          const nodeId = child.getNodeId();
          if (nodeId in initData) {
            child.setPosition(initData[nodeId].position);
            child.setSkipNode(false);
          } else {
            child.setPosition(-1);
            child.setSkipNode(true);
          }
        });
      }
    },

    __show: function(itemMdl) {
      itemMdl.set({
        skipNode: true
      });
    },

    __hide: function(itemMdl) {
      itemMdl.set({
        skipNode: false
      });
    },

    __moveUp: function(itemMdl) {
      const nodeId = itemMdl.getNodeId();
      const parentMdl = this.__tree.getParent(itemMdl);
      if (parentMdl) {
        const children = parentMdl.getChildren().toArray();
        const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
        if (idx > 0) {
          this.self().moveElement(children, idx, idx-1);
        }
      }
    },

    __moveDown: function(itemMdl) {
      const nodeId = itemMdl.getNodeId();
      const parentMdl = this.__tree.getParent(itemMdl);
      if (parentMdl) {
        const children = parentMdl.getChildren().toArray();
        const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
        if (idx < children.length-1) {
          this.self().moveElement(children, idx, idx+1);
        }
      }
    },

    __recalculatePositions: function() {
      const rootModel = this.__tree.getModel();
      let children = [];
      this.self().getItemsInTree(rootModel, children);
      children.shift();
      let pos = 0;
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        if (child.getSkipNode() === false) {
          child.setPosition(pos);
          pos++;
        }
      }
      this.__tree.refresh();
    },

    __enableSlides: function() {
      let slideshow = {};
      const model = this.__tree.getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        if (child.getSkipNode() === false) {
          slideshow[child.getNodeId()] = {
            "position": child.getPosition()
          };
        }
      });
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getUi().setSlideshow(slideshow);
      this.fireEvent("finished");
    },

    __disableSlides: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getUi().setSlideshow({});
      this.fireEvent("finished");
    }
  }
});
