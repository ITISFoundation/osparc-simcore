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
 *
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorActions", {
  extend: qx.ui.core.Widget,

  construct: function(simulator) {
    this.base(arguments);

    this.set({
      simulator: simulator
    });

    this._setLayout(new qx.ui.layout.HBox());

    const actions = new qx.ui.toolbar.ToolBar();
    this._add(actions, {
      flex: 1
    });

    const newSettings = this.__newSettings = new qx.ui.toolbar.MenuButton(this.tr("New Settings")).set({
      enabled: false
    });
    actions.add(newSettings);

    const writeInputFile = this.__writeInputFile = new qx.ui.toolbar.Button(this.tr("Write file"));
    writeInputFile.addListener("execute", () => {
      this.fireEvent("writeFile");
    }, this);
    actions.add(writeInputFile);
  },

  properties: {
    simulator: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    node: {
      check: "qxapp.data.model.Node",
      nullable: true
    }
  },

  events: {
    "newSetting": "qx.event.type.Data",
    "writeFile": "qx.event.type.Event"
  },

  members: {
    __newSettings: null,

    setContextNode: function(node) {
      this.setNode(node);

      this.__updateNewSettings();
    },

    __updateNewSettings: function() {
      const newSettings = this.__newSettings;
      newSettings.resetMenu();
      const node = this.getNode();
      if (node && node.hasInputsDefault()) {
        const store = qxapp.store.Store.getInstance();
        const inputs = node.getInputsDefault();
        newSettings.setEnabled(true);
        const menu = new qx.ui.menu.Menu();
        for (const inputKey in inputs) {
          const simKey = this.getSimulator().getKey();
          const itemList = store.getItemList(simKey, inputKey);
          for (let i=0; i<itemList.length; i++) {
            const item = itemList[i];
            const btn = new qx.ui.menu.Button(item.label);
            btn.addListener("execute", () => {
              const data = {
                settingKey: node.getKey(),
                itemKey: item.key
              };
              this.fireDataEvent("newSetting", data);
            });
            menu.add(btn);
          }
        }
        newSettings.setMenu(menu);
      } else {
        newSettings.setEnabled(false);
      }
    }
  }
});
