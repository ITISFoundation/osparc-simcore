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
 * Widget used for showing ConceptSettings (props and tree) from GlobalSettings
 *
 */

qx.Class.define("qxapp.component.widget.simulator.ConceptSettings", {
  extend: qx.ui.core.Widget,

  construct: function(node, settingKey) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      node: node,
      settingKey: settingKey
    });
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    settingKey: {
      check: "String",
      apply: "_applySettingKey",
      nullable: true
    }
  },

  members: {
    __tree: null,

    getTree: function() {
      return this.__tree;
    },

    _applySettingKey: function() {
      this._removeAll();

      const label = new qx.ui.basic.Label(this.tr("Properties")).set({
        allowGrowX: true,
        appearance: "toolbar-textfield"
      });
      this._add(label);

      const settKey = this.getSettingKey();
      if (settKey) {
        const label2 = new qx.ui.basic.Label(this.tr("Properties2")).set({
          allowGrowX: true,
          appearance: "toolbar-textfield"
        });
        this._add(label2);
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
