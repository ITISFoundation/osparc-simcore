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

  construct: function(pricingUnitsData, preselectedPricingUnit, changeSelectionAllowed = true) {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.HBox(10),
      allowGrowY: false,
    });

    this.__buildLayout(pricingUnitsData, preselectedPricingUnit, changeSelectionAllowed);
  },

  properties: {
    selectedUnitId: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeSelectedUnitId"
    }
  },

  members: {
    __buildLayout: function(pricingUnitsData, preselectedPricingUnit, changeSelectionAllowed) {
      const pricingUnitTiers = [];
      pricingUnitsData.forEach(pricingUnitData => {
        const pricingUnit = new osparc.data.model.PricingUnit(pricingUnitData);
        const pricingUnitTier = new osparc.study.PricingUnitTier(pricingUnit).set({
          showSelectButton: changeSelectionAllowed,
        });
        pricingUnitTiers.push(pricingUnitTier);
        this._add(pricingUnitTier);
      });

      if (preselectedPricingUnit) {
        const pricingUnitTierFound = pricingUnitTiers.find(pricingUnitTier => pricingUnitTier.getUnitData().getPricingUnitId() === preselectedPricingUnit["pricingUnitId"]);
        if (pricingUnitTierFound) {
          pricingUnitTierFound.setSelected(true);
        }
      } else {
        // preselect default
        pricingUnitTiers.forEach(pricingUnitTier => {
          if (pricingUnitTier.getUnitData().getIsDefault()) {
            pricingUnitTier.setSelected(true);
          }
        });
      }

      pricingUnitTiers.forEach(pricingUnitTier => {
        pricingUnitTier.addListener("selectPricingUnit", () => {
          if (changeSelectionAllowed) {
            const selectedUnitId = pricingUnitTier.getUnitData().getPricingUnitId();
            this.setSelectedUnitId(selectedUnitId);
          } else {
            pricingUnitTiers.forEach(btn => btn.setSelected(btn.getUnitData().getIsDefault()));
          }
        });
      });
    }
  }
});
