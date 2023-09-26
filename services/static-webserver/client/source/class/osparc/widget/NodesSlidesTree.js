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


qx.Class.define("osparc.widget.NodesSlidesTree", {
  extend: qx.ui.core.Widget,

  construct: function(study) {
    this.base(arguments);

    this.__study = study;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("instructions");

    this.__tree = this.getChildControl("tree");

    const disable = this.getChildControl("disable");
    disable.addListener("execute", () => this.__disableSlides(), this);
    const enable = this.getChildControl("save-button");
    enable.addListener("execute", () => this.__enableSlides(), this);

    const model = this.__initRoot();
    this.__tree.setModel(model);

    this.__initTree();
    this.__initData();
  },

  events: {
    "changeSelectedNode": "qx.event.type.Data",
    "finished": "qx.event.type.Event"
  },

  members: {
    __study: null,
    __tree: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "instructions": {
          let msg = this.tr("Use the eye icons to display/hide nodes in the App Mode.");
          msg += "<br>";
          msg += this.tr("Use the up and down arrows to sort them.");
          msg += "<br>";
          msg += this.tr("You can also display nodes by clicking on them on the Workbench or Nodes list.");
          control = new qx.ui.basic.Label(msg).set({
            rich: true,
            wrap: true,
            paddingLeft: 5,
            paddingRight: 5
          });
          this._add(control);
          break;
        }
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
        case "save-button": {
          control = new qx.ui.form.Button(this.tr("Save")).set({
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
        position: null,
        instructions: null
      };
      return qx.data.marshal.Json.createModel(rootData, true);
    },

    __initTree: function() {
      this.__tree.setDelegate({
        createItem: () => new osparc.widget.NodeSlideTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("nodeId", "nodeId", null, item, id);
          c.bindProperty("label", "label", null, item, id);
          c.bindProperty("position", "position", null, item, id);
          c.bindProperty("instructions", "instructions", null, item, id);
        },
        configureItem: item => {
          item.addListener("showNode", () => this.__itemActioned(item, "show"), this);
          item.addListener("hideNode", () => this.__itemActioned(item, "hide"), this);
          item.addListener("moveUp", () => this.__itemActioned(item, "moveUp"), this);
          item.addListener("moveDown", () => this.__itemActioned(item, "moveDown"), this);
          item.addListener("saveInstructions", e => this.__saveInstructions(item, e.getData()), this);
          item.addListener("tap", () => this.fireDataEvent("changeSelectedNode", item.getNodeId()), this);
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
        const instructions = this.__study.getUi().getSlideshow().getInstructions(nodeId);
        nodeInTree.instructions = instructions;
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

    changeSelectedNode: function(nodeId) {
      const children = this.__tree.getModel().getChildren().toArray();
      const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
      if (idx > -1) {
        const item = children[idx];
        this.__tree.setSelection(new qx.data.Array([item]));
        // show by default
        if (item.getPosition() === -1) {
          this.__show(item);
          this.__tree.refresh();
        }
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

    __saveInstructions: function(item, instructions) {
      const itemMdl = item.getModel();
      itemMdl.setInstructions(instructions);
    },

    __serialize: function() {
      const slideshow = {};
      const model = this.__tree.getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        slideshow[child.getNodeId()] = {
          "position": child.getPosition(),
          "instructions": child.getInstructions()
        };
      });
      return slideshow;
    },

    __enableSlides: function() {
      const slideshow = this.__serialize();
      this.__study.getUi().getSlideshow().setData(slideshow);
      this.fireEvent("finished");
    },

    __disableSlides: function() {
      this.__getVisibleItems().forEach(item => {
        item.setPosition(-1);
      });
      const slideshow = this.__serialize();
      this.__study.getUi().getSlideshow().setData(slideshow);
      this.fireEvent("finished");
    }
  }
});
