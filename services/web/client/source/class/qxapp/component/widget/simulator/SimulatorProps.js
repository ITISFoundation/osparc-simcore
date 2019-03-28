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
 * Widget used for showing SimulatorProps (props and tree) from SimulatorTree
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorProps", {
  extend: qx.ui.core.Widget,

  construct: function(node, settings) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      node: node,
      settings: settings
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    settings: {
      check: "qx.core.Object",
      apply: "_applySettings",
      nullable: true
    }
  },

  members: {
    __tree: null,

    getTree: function() {
      return this.__tree;
    },

    _applySettings: function() {
      this._removeAll();

      const label = new qx.ui.basic.Label(this.tr("Properties")).set({
        allowGrowX: true,
        appearance: "toolbar-textfield"
      });
      this._add(label);

      const settKey = this.getSettings();
      if (settKey) {
        // const metaData = qxapp.data.Store.getInstance().getItem(this.getKey(), settKey);
        const metaData = this.getSettings();
        if (metaData) {
          console.log(metaData);
          /*
          if (metaData.inputsDefault) {
            this.__addInputsDefault(metaData.inputsDefault);
          }
          */
          const label2 = new qx.ui.basic.Label(this.tr("Properties2")).set({
            allowGrowX: true,
            appearance: "toolbar-textfield"
          });
          this._add(label2);
        }
      }
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
        children: children
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.__tree.setModel(model);
    }
  }
});
