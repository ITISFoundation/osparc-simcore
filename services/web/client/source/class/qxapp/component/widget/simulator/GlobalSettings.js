/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget/VirtualTree used for showing GlobalSettings from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.GlobalSettings", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.VBox());

    const label = new qx.ui.basic.Label(this.tr("Explorer")).set({
      allowGrowX: true,
      appearance: "toolbar-textfield"
    });
    this._add(label);

    const tree = this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children");
    tree.set({
      openMode: "none"
    });
    tree.setDelegate({
      createItem: () => new qxapp.component.widget.simulator.GlobalSettingsTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("metadata", "metadata", null, item, id);
      }
    });
    tree.addListener("tap", this.__selectionChanged, this);
    this.__populateTree();

    this._add(tree, {
      flex: 1
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Data"
  },

  members: {
    __tree: null,

    getTree: function() {
      return this.__tree;
    },

    __populateTree: function() {
      const store = qxapp.data.Store.getInstance();
      const itemList = store.getItemList(this.getNode().getKey());
      let children = [];
      for (let i=0; i<itemList.length; i++) {
        children.push({
          label: itemList[i].label,
          key: itemList[i].key,
          metadata: store.getItem(this.getNode().getKey(), itemList[i].key),
          children: []
        });
      }
      let data = {
        label: "Simulator",
        key: null,
        metadata: null,
        children: children
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.__tree.setModel(model);
    },

    __selectionChanged: function() {
      const currentSelection = this.__getOneSelectedRow();
      if (currentSelection) {
        this.fireDataEvent("selectionChanged", currentSelection.getMetadata());
      }
    },

    __getOneSelectedRow: function() {
      const selection = this.__tree.getSelection();
      if (selection && selection.toArray().length > 0) {
        return selection.toArray()[0];
      }
      return null;
    }
  }
});
