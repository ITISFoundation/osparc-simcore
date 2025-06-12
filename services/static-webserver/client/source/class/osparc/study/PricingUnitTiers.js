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

qx.Class.define("osparc.study.PricingUnitTiers", {
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
      event: "changeSelectedUnitId",
      apply: "__applySelectedUnitId",
    }
  },

  events: {
    "selectPricingUnitRequested": "qx.event.type.Event",
  },

  members: {
    __pricingUnitTiers: null,

    __buildLayout: function(pricingUnitsData, preselectedPricingUnit, changeSelectionAllowed) {
      const pricingUnitTiers = this.__pricingUnitTiers = [];
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
            this.fireDataEvent("selectPricingUnitRequested", pricingUnitTier.getUnitData());
          }
        });
      });
    },

    __applySelectedUnitId: function(selectedUnitId) {
      // select and unselect the rest
      this.__pricingUnitTiers.forEach(puTIer => puTIer.setSelected(puTIer.getUnitData().getPricingUnitId() === selectedUnitId));
    },

    getSelectedUnit: function() {
      const selectedUnitTier = this.__pricingUnitTiers.find(puTier => puTier.isSelected());
      if (selectedUnitTier) {
        return selectedUnitTier.getUnitData();
      }
      return null;
    },
  }
});
