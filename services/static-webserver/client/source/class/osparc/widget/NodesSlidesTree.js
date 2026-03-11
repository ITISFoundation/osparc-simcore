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

    const tree = this.getChildControl("tree");

    const disableAppModeButton = this.getChildControl("disable");
    disableAppModeButton.addListener("execute", () => this.__disableSlides(), this);

    const closeButton = this.getChildControl("close-button");
    closeButton.addListener("execute", () => this.fireEvent("close"), this);

    const model = this.__initRoot();
    tree.setModel(model);
    this.__initTree();
    this.__initData();
  },

  events: {
    "changeSelectedNode": "qx.event.type.Data",
    "close": "qx.event.type.Event",
  },

  members: {
    __study: null,

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
          control = new qx.ui.tree.VirtualTree(null, "label", "children").set({
            hideRoot: true,
            decorator: "service-tree",
            openMode: "none",
            contentPadding: 0,
            padding: 0,
            backgroundColor: "background-main-2"
          });
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
          control = new qx.ui.form.Button(this.tr("Disable App Mode")).set({
            allowGrowX: false,
            appearance: "no-shadow-button"
          });
          const buttons = this.getChildControl("buttons");
          buttons.add(control);
          break;
        }
        case "close-button": {
          control = new qx.ui.form.Button(this.tr("Close")).set({
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
      this.getChildControl("tree").setDelegate({
        createItem: () => new osparc.widget.NodeSlideTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("nodeId", "nodeId", null, item, id);
          c.bindProperty("label", "label", null, item, id);
          c.bindProperty("position", "position", null, item, id);
          c.bindProperty("instructions", "instructions", null, item, id);
        },
        configureItem: item => {
          item.addListener("showNode", () => this.__stepUpdated(item, "show"), this);
          item.addListener("hideNode", () => this.__stepUpdated(item, "hide"), this);
          item.addListener("moveUp", () => this.__stepUpdated(item, "moveUp"), this);
          item.addListener("moveDown", () => this.__stepUpdated(item, "moveDown"), this);
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

      const tree = this.getChildControl("tree");
      tree.getModel().getChildren().removeAll();
      const allChildren = this.__convertToModel(topLevelNodes);
      tree.getModel().setChildren(qx.data.marshal.Json.createModel(allChildren));

      tree.refresh();
    },

    changeSelectedNode: function(nodeId) {
      const tree = this.getChildControl("tree");
      const children = tree.getModel().getChildren().toArray();
      const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
      if (idx > -1) {
        const item = children[idx];
        tree.setSelection(new qx.data.Array([item]));
        // show by default
        if (item.getPosition() === -1) {
          this.__stepUpdated(item, "show");
        }
      }
    },

    __stepUpdated: function(item, action) {
      const itemMdl = item.getModel ? item.getModel() : item;
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
        const changed = fnct.call(this, itemMdl);
        if (changed) {
          this.getChildControl("tree").refresh();
          this.__saveSlides();
        }
      }
    },

    __getVisibleItems: function() {
      const children = this.getChildControl("tree").getModel().getChildren().toArray();
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
      const children = this.getChildControl("tree").getModel().getChildren().toArray();
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
      const children = this.getChildControl("tree").getModel().getChildren().toArray();
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

    __saveSlides: function() {
      const slideshow = this.__serialize();
      this.__study.getUi().getSlideshow().setData(slideshow);
      this.__study.getUi().getSlideshow().fireEvent("changeSlideshow");
    },

    __saveInstructions: function(item, instructions) {
      const itemMdl = item.getModel();
      itemMdl.setInstructions(instructions);

      // save instructions
      const nodeId = itemMdl.getNodeId();
      this.__study.getUi().getSlideshow().setInstructions(nodeId, instructions);
      this.__study.getUi().getSlideshow().fireEvent("changeSlideshow");
    },

    __serialize: function() {
      const slideshow = {};
      const model = this.getChildControl("tree").getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        slideshow[child.getNodeId()] = {
          "position": child.getPosition(),
          "instructions": child.getInstructions()
        };
      });
      return slideshow;
    },

    __disableSlides: function() {
      this.__getVisibleItems().forEach(item => {
        item.setPosition(-1);
      });
      const slideshow = this.__serialize();
      this.__study.getUi().getSlideshow().setData(slideshow);
      this.fireEvent("close");
    }
  }
});
