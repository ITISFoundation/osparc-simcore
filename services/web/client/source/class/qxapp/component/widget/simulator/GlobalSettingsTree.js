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
 * VirtualTree used for showing GlobalSettingsTree from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.GlobalSettingsTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function(node) {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      node: node
    });

    this.setDelegate({
      createItem: () => new qxapp.component.widget.GlobalSettingsTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("metadata", "metadata", null, item, id);
      }
    });
    this.addListener("tap", this.__selectionChanged, this);

    this.__populateTree();
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
        children: children
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.setModel(model);
    },

    __selectionChanged: function() {
      const currentSelection = this.__getOneSelectedRow();
      if (currentSelection) {
        this.fireDataEvent("selectionChanged", currentSelection.getModel());
      }
    },

    __getOneSelectedRow: function() {
      const selection = this.getSelection();
      if (selection && selection.toArray().length > 0) {
        return selection.toArray()[0];
      }
      return null;
    }
  }
});
