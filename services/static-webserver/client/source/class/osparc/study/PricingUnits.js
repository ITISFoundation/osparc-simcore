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

qx.Class.define("osparc.study.PricingUnits", {
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
    selectedUnit: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeSelectedUnit"
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
        const button = new osparc.study.PricingUnit(pricingUnit);
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
          const selectedUnit = button.getPricingUnit();
          this.setSelectedUnit(selectedUnit);
        }
      }));

      // preselect default
      buttons.forEach(button => {
        if (button.getPricingUnit()["default"]) {
          button.execute();
        }
      });
    }
  }
});
