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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.__tree = this._createChildControlImpl("tree");

    const model = this.__initTree();
    this.__tree.setModel(model);

    this.__populateTree();
  },

  statics: {
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

    __initTree: function() {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const topLevelNodes = study.getWorkbench().getNodes();
      let data = {
        label: study.getName(),
        children: osparc.component.widget.NodesTree.convertModel(topLevelNodes),
        nodeId: study.getUuid(),
        isContainer: true
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      return model;
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
        },
        configureItem: item => {
          item.addListener("moveUp", () => {
            const nodeId = item.getModel().getNodeId();
            const parent = this.__tree.getParent(item.getModel());
            if (parent) {
              const children = parent.getChildren().toArray();
              const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
              if (idx > 0) {
                this.self().moveElement(children, idx, idx-1);
                item.setPosition(idx-1);
                this.__tree.refresh();
              }
            }
          }, this);
          item.addListener("moveDown", () => {
            const nodeId = item.getModel().getNodeId();
            const parent = this.__tree.getParent(item.getModel());
            if (parent) {
              const children = parent.getChildren().toArray();
              const idx = children.findIndex(elem => elem.getNodeId() === nodeId);
              if (idx < children.length-1) {
                this.self().moveElement(children, idx, idx+1);
                item.setPosition(idx+1);
                this.__tree.refresh();
              }
            }
          }, this);
        }
      });
    }
  }
});
