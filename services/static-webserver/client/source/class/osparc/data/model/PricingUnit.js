/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores PricingUnit data.
 */

qx.Class.define("osparc.data.model.PricingUnit", {
  extend: qx.core.Object,

  /**
   * @param pricingUnitData {Object} Object containing the serialized PricingUnit Data
   */
  construct: function(pricingUnitData) {
    this.base(arguments);

    this.set({
      pricingUnitId: pricingUnitData.pricingUnitId,
      name: pricingUnitData.unitName,
      cost: parseFloat(pricingUnitData.currentCostPerUnit),
      isDefault: pricingUnitData.default,
      extraInfo: pricingUnitData.unitExtraInfo,
    });
  },

  properties: {
    pricingUnitId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changePricingUnitId"
    },

    classification: {
      check: ["TIER", "LICENSE"],
      nullable: false,
      init: null,
      event: "changeClassification"
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeName"
    },

    cost: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeCost"
    },

    isDefault: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsDefault",
    },

    extraInfo: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeExtraInfo"
    },
  },
});
