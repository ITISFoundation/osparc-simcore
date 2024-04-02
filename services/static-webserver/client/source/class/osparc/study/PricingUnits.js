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

  construct: function(pricingUnits, preselectedPricingUnit) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.HBox(5)
    });

    this.__buildLayout(pricingUnits, preselectedPricingUnit);
  },

  properties: {
    selectedUnit: {
      check: "Object",
      init: null,
      nullable: false,
      event: "changeSelectedUnit"
    }
  },

  members: {
    __buildLayout: function(pricingUnits, preselectedPricingUnit) {
      const buttons = [];
      pricingUnits.forEach(pricingUnit => {
        const button = new osparc.study.PricingUnit(pricingUnit);
        buttons.push(button);
        this._add(button);
      });

      const groupOptions = new qx.ui.form.RadioGroup();
      buttons.forEach(btn => groupOptions.add(btn));

      if (preselectedPricingUnit) {
        const buttonFound = buttons.find(button => button.getPricingUnitId() === preselectedPricingUnit["pricingUnitId"]);
        if (buttonFound) {
          buttonFound.execute();
        }
      } else {
        // preselect default
        buttons.forEach(button => {
          if (button.getPricingUnitData()["default"]) {
            button.execute();
          }
        });
      }

      buttons.forEach(button => button.addListener("changeValue", e => {
        if (e.getData()) {
          const selectedUnit = button.getPricingUnitData();
          this.setSelectedUnit(selectedUnit);
        }
      }));
    }
  }
});
