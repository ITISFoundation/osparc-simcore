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


qx.Class.define("osparc.component.widget.NodesSlidesTree", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this.__study = study;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__tree = this.getChildControl("tree");

    const disable = this.getChildControl("disable");
    disable.addListener("execute", () => this.__disableSlides(), this);
    const enable = this.getChildControl("enable");
    enable.addListener("execute", () => this.__enableSlides(), this);

    const model = this.__initRoot();
    this.__tree.setModel(model);

    this.__initTree();
    this.__initData();
  },

  events: {
    "finished": "qx.event.type.Event"
  },

  statics: {
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
    __study: null,
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
        hideRoot: true,
        decorator: "service-tree",
        openMode: "none",
        contentPadding: 0,
        padding: 0,
        backgroundColor: "background-main-2"
      });
      return tree;
    },

    __initRoot: function() {
      const study = this.__study;
      let rootData = {
        label: study.getName(),
        children: [],
        nodeId: study.getUuid(),
        position: null
      };
      return qx.data.marshal.Json.createModel(rootData, true);
    },

    __initTree: function() {
      this.__tree.setDelegate({
        createItem: () => new osparc.component.widget.NodeSlideTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("nodeId", "nodeId", null, item, id);
          c.bindProperty("label", "label", null, item, id);
          c.bindProperty("position", "position", null, item, id);
        },
        configureItem: item => {
          item.addListener("showNode", () => this.__itemActioned(item, "show"), this);
          item.addListener("hideNode", () => this.__itemActioned(item, "hide"), this);
          item.addListener("moveUp", () => this.__itemActioned(item, "moveUp"), this);
          item.addListener("moveDown", () => this.__itemActioned(item, "moveDown"), this);
        },
        sorter: (a, b) => {
          const aPos = a.getPosition();
          if (aPos === -1) {
            return 1;
          }
          const bPos = b.getPosition();
          if (bPos === -1) {
            return -1;
          }
          return aPos - bPos;
        }
      });
    },

    /**
     * Converts an object of nodes into an array of children to be consumed by the tree model.
     * The tree is expecting to bind the children into NodeSlideTreeItem with nodeId and position as props.
     * @param {Object.<Nodes>} nodes Object with nodes <nodeId: node>
     * @returns {Array} Array of objects with label, nodeId and position.
     */
    __convertToModel: function(nodes) {
      const children = [];
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        const nodeInTree = {
          label: node.getLabel(),
          nodeId: node.getNodeId()
        };
        const pos = this.__study.getUi().getSlideshow().getPosition(nodeId);
        nodeInTree.position = pos;
        children.push(nodeInTree);
      }
      return children;
    },

    __initData: function() {
      const topLevelNodes = this.__study.getWorkbench().getNodes();

      this.__tree.getModel().getChildren().removeAll();
      const allChildren = this.__convertToModel(topLevelNodes);
      this.__tree.getModel().setChildren(qx.data.marshal.Json.createModel(allChildren));

      this.__tree.refresh();
    },

    nodeSelected: function(nodeId) {
      const children = this.__tree.getModel().getChildren().toArray();
      const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
      if (idx > -1) {
        this.__tree.setSelection(new qx.data.Array([children[idx]]));
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
      this.nodeSelected(item.getModel().getNodeId());
      if (fnct.call(this, item.getModel())) {
        this.__tree.refresh();
      }
    },

    __getVisibleItems: function() {
      const children = this.__tree.getModel().getChildren().toArray();
      return children.filter(elem => elem.getPosition() !== -1);
    },

    __show: function(itemMdl) {
      const last = this.__getVisibleItems().length;
      itemMdl.setPosition(last);
      return true;
    },

    __hide: function(itemMdl) {
      const oldPos = itemMdl.getPosition();
      itemMdl.setPosition(-1);
      // the rest moves one pos up
      this.__getVisibleItems().forEach(item => {
        const p = item.getPosition();
        if (p >= oldPos) {
          item.setPosition(p-1);
        }
      });
      return true;
    },

    __moveUp: function(itemMdl) {
      const children = this.__tree.getModel().getChildren().toArray();
      const nodeId = itemMdl.getNodeId();
      const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
      if (idx > -1) {
        const oldPos = children[idx].getPosition();
        const newPos = oldPos-1;
        if (newPos === -1) {
          return false;
        }
        const idx2 = children.findIndex(elem => elem.getPosition() === newPos);
        if (idx2 > -1) {
          children[idx].setPosition(newPos);
          children[idx2].setPosition(oldPos);
          return true;
        }
      }
      return false;
    },

    __moveDown: function(itemMdl) {
      const children = this.__tree.getModel().getChildren().toArray();
      const nodeId = itemMdl.getNodeId();
      const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
      if (idx > -1) {
        const oldPos = children[idx].getPosition();
        const newPos = oldPos+1;
        if (newPos === this.__getVisibleItems().length) {
          return false;
        }
        const idx2 = children.findIndex(elem => elem.getPosition() === newPos);
        if (idx2 > -1) {
          children[idx].setPosition(newPos);
          children[idx2].setPosition(oldPos);
          return true;
        }
      }
      return false;
    },

    __serialize: function() {
      const slideshow = {};
      const model = this.__tree.getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        if (child.getPosition() !== -1) {
          slideshow[child.getNodeId()] = {
            "position": child.getPosition()
          };
        }
      });
      return slideshow;
    },

    __enableSlides: function() {
      const slideshow = this.__serialize();
      this.__study.getUi().getSlideshow().setData(slideshow);
      this.fireEvent("finished");
    },

    __disableSlides: function() {
      this.__study.getUi().getSlideshow().setData({});
      this.fireEvent("finished");
    }
  }
});
