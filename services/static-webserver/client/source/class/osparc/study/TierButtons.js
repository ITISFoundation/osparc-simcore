/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.study.TierButtons", {
  extend: qx.ui.container.Composite,

  construct: function(pricingUnits) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.HBox(5)
    });

    this.__pricingUnits = pricingUnits;

    this.__buildLayout();
  },

  properties: {
    selectedTier: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeSelectedTier"
    },

    advanced: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeAdvanced"
    }
  },

  members: {
    __pricingUnit: null,

    __buildLayout: function() {
      const pricingUnits = this.__pricingUnits;

      const buttons = [];
      pricingUnits.forEach(pricingUnit => {
        const button = new osparc.study.TierButton(pricingUnit);
        this.bind("advanced", button, "advanced");
        buttons.push(button);
        this._add(button);
      });

      const buttonSelected = button => {
        buttons.forEach(btn => {
          if (btn !== button) {
            btn.setValue(false);
          }
        });
      };
      buttons.forEach(button => button.addListener("execute", () => buttonSelected(button)));
      buttons.forEach(button => button.addListener("changeValue", e => {
        if (e.getData()) {
          this.setSelectedTier(button.getTierInfo());
        }
      }));

      // preselect default
      buttons.forEach(button => {
        if (button.getTierInfo()["default"]) {
          button.execute();
        }
      });
    }
  }
});
