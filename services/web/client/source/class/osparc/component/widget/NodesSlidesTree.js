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
    const save = this._createChildControlImpl("save-button");
    save.addListener("execute", () => this.__saveSlides(), this);

    const model = this.__initTree(initData);
    this.__tree.setModel(model);

    this.__populateTree();
  },

  statics: {
    convertModel: function(nodes) {
      let children = [];
      let i=0;
      for (let nodeId in nodes) {
        const node = nodes[nodeId];
        let nodeInTree = {
          label: "",
          nodeId: node.getNodeId(),
          skipNode: false,
          position: i
        };
        nodeInTree.label = node.getLabel();
        if (node.isContainer()) {
          nodeInTree.children = this.convertModel(node.getInnerNodes());
        }
        children.push(nodeInTree);
        i++;
      }
      return children;
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
        case "save-button":
          control = new qx.ui.form.Button(this.tr("Save")).set({
            allowGrowX: false,
            alignX: "right"
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __buildTree: function() {
      const tree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        decorator: "service-tree",
        openMode: "none",
        contentPadding: 0,
        padding: 0
      });
      return tree;
    },

    __initTree: function(initData) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const topLevelNodes = study.getWorkbench().getNodes();
      let rootData = {
        label: study.getName(),
        children: this.self().convertModel(topLevelNodes),
        nodeId: study.getUuid(),
        skipNode: null,
        position: null
      };
      const children = rootData.children;
      for (let nodeId in initData) {
        const idx = children.findIndex(child => child.nodeId === nodeId);
        if (idx > -1) {
          children[idx].position = initData[nodeId].position;
          children[idx].skipNode = initData[nodeId].skipNode;
        }
      }
      return qx.data.marshal.Json.createModel(rootData, true);
    },

    __populateTree: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();

      let i = 0;
      this.__tree.setDelegate({
        createItem: () => {
          const nodeSlideTreeItem = new osparc.component.widget.NodeSlideTreeItem();
          nodeSlideTreeItem.set({
            skipNode: false,
            position: i
          });
          i++;
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
      const treeMdl = this.__tree.getModel();
      const children = treeMdl.getChildren().toArray();
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

    __saveSlides: function() {
      let slideshow = {};
      const model = this.__tree.getModel();
      const children = model.getChildren().toArray();
      children.forEach(child => {
        if (child.getSkipNode() === false) {
          slideshow[child.getNodeId()] = {
            "slideType": "slide",
            "position": child.getPosition()
          };
        }
      });
      console.log("Serialize me", slideshow);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const studyUI = study.getUi();
      studyUI["slideshow"] = slideshow;
    }
  }
});
