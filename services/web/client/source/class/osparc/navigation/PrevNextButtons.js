/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.navigation.PrevNextButtons", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(0).set({
      alignY: "middle"
    }));
  },

  events: {
    "nodeSelected": "qx.event.type.Data"
  },

  statics: {
    BUTTON_OPTIONS: {
      font: "text-14",
      allowGrowY: false,
      minWidth: 32,
      minHeight: 32
    }
  },

  members: {
    __prvsBtn: null,
    __nextBtn: null,
    __currentNodeId: null,

    populateButtons: function(nodesIds) {
      this.__createButtons();

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const currentNodeId = study.getUi().getCurrentNodeId();
      const currentIdx = nodesIds.indexOf(currentNodeId);

      if (currentIdx > 0) {
        this.__prvsBtn.addListener("execute", () => {
          this.fireDataEvent("nodeSelected", nodesIds[currentIdx-1]);
        }, this);
      } else {
        this.__prvsBtn.setEnabled(false);
      }

      if (currentIdx < nodesIds.length-1) {
        this.__nextBtn.addListener("execute", () => {
          this.fireDataEvent("nodeSelected", nodesIds[currentIdx+1]);
        }, this);
      } else {
        this.__nextBtn.setEnabled(false);
      }
    },

    __createButtons: function() {
      this._removeAll();

      const prvsBtn = this.__prvsBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Previous"),
        icon: "@FontAwesome5Solid/arrow-left/24",
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        allowGrowX: false
      });
      this._add(prvsBtn);

      const nextBtn = this.__nextBtn = new qx.ui.form.Button().set({
        toolTipText: this.tr("Next"),
        icon: "@FontAwesome5Solid/arrow-right/24",
        ...osparc.navigation.NavigationBar.BUTTON_OPTIONS,
        allowGrowX: false
      });
      this._add(nextBtn);
    }
  }
});
