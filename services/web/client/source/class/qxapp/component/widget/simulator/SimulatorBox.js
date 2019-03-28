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
 * Widget/VirtualTree used for showing SimulatorTree from Simulator
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorBox", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    this._setLayout(new qx.ui.layout.Canvas());
    const splitpane = this.__splitpane = new qx.ui.splitpane.Pane("vertical");
    splitpane.getChildControl("splitter").getChildControl("knob")
      .hide();
    splitpane.setOffset(0);

    this._add(splitpane, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
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
