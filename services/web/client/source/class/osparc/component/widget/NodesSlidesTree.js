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

  construct: function(slideShow) {
    this.base(arguments);

    this.__slideShow = slideShow;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__tree = this.getChildControl("tree");
    const disable = this.getChildControl("disable");
    disable.addListener("execute", () => this.__disableSlides(), this);
    const enable = this.getChildControl("enable");
    enable.addListener("execute", () => this.__enableSlides(), this);

    const model = this.__initRoot();
    this.__tree.setModel(model);

    this.__initTree();
    this.__recalculatePositions();

    this.__initData();
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
    __slideShow: null,

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

    __initRoot: function() {
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

    __initTree: function() {
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
            this.__itemActioned(item, "show");
          }, this);
          item.addListener("hideNode", () => {
            this.__itemActioned(item, "hide");
          }, this);
          item.addListener("moveUp", () => {
            this.__itemActioned(item, "moveUp");
          }, this);
          item.addListener("moveDown", () => {
            this.__itemActioned(item, "moveDown");
          }, this);
        }
      });
    },

    __initData: function() {
      if (!this.__slideShow.isEmpty()) {
        const initData = this.__slideShow.getData();
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
        children.sort((a, b) => {
          const aPos = a.getPosition();
          const bPos = b.getPosition();
          if (aPos === -1) {
            return 1;
          }
          if (bPos === -1) {
            return -1;
          }
          return aPos - bPos;
        });
        this.__tree.refresh();
      }
    },

    __itemActioned: function(item, action) {
      let fnct;
      switch (action) {
        case "show":
          fnct = this.__show;
          break;
        case "hide":
          fnct = this.__hide;
          break;
        case "moveUp":
          fnct = this.__moveUp;
          break;
        case "moveDown":
          fnct = this.__moveDown;
          break;
      }
      if (fnct) {
        this.__tree.setSelection(new qx.data.Array([item.getModel()]));
        fnct.call(this, item.getModel());
        this.__recalculatePositions();
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

    __serialize: function() {
      const slideshow = {};
      const model = this.__tree.getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        if (child.getSkipNode() === false) {
          slideshow[child.getNodeId()] = {
            "position": child.getPosition()
          };
        }
      });
      return slideshow;
    },

    __enableSlides: function() {
      const slideshow = this.__serialize();
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getUi().getSlideshow().setData(slideshow);
      this.fireEvent("finished");
    },

    __disableSlides: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getUi().getSlideshow().setData({});
      this.fireEvent("finished");
    }
  }
});
