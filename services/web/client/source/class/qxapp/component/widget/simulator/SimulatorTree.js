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
 * VirtualTree used for showing SimulatorTree from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function(node) {
    this.base(arguments, null, "label", "children");

    this.set({
      node: node
    });

    this.set({
      openMode: "none"
    });
    this.setDelegate({
      createItem: () => new qxapp.component.widget.simulator.SimulatorTreeItem(),
      bindItem: (c, item, id) => {
        c.bindDefaultProperties(item, id);
        c.bindProperty("key", "model", null, item, id);
        c.bindProperty("version", "version", null, item, id);
        c.bindProperty("metadata", "metadata", null, item, id);
        item.createNode();
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
        const metadata = store.getItem(this.getNode().getKey(), itemList[i].key);
        let newEntry = {
          key: itemList[i].key,
          version: itemList[i].version,
          metadata: metadata
        };
        if ("inputs" in metadata && "mapper" in metadata.inputs) {
          newEntry["children"] = [];
        }
        children.push(newEntry);
      }
      let data = {
        label: "Simulator",
        key: null,
        metadata: null,
        children: children
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.setModel(model);
    },

    __selectionChanged: function(e) {
      const selection = e.getTarget();
      if ("getNode" in selection) {
        this.fireDataEvent("selectionChanged", selection.getNode());
      } else {
        this.fireDataEvent("selectionChanged", null);
      }
    }
  }
});
