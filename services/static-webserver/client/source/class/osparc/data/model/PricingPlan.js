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
 * Class that stores PricingPlan data.
 */

qx.Class.define("osparc.data.model.PricingPlan", {
  extend: qx.core.Object,

  /**
   * @param pricingPlanData {Object} Object containing the serialized PricingPlan Data
   */
  construct: function(pricingPlanData) {
    this.base(arguments);

    this.set({
      pricingPlanId: pricingPlanData.pricingPlanId,
      pricingPlanKey: pricingPlanData.pricingPlanKey,
      pricingUnits: pricingPlanData.pricingUnits || [],
      classification: pricingPlanData.displayName.includes("ViP") ? "LICENSE" : pricingPlanData.classification,
      name: pricingPlanData.displayName,
      description: pricingPlanData.description,
      isActive: pricingPlanData.isActive,
    });
  },

  properties: {
    pricingPlanId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changePricingPlanId"
    },

    pricingPlanKey: {
      check: "String",
      nullable: true,
      init: null,
      event: "changePricingPlanKey"
    },

    pricingUnits: {
      check: "Array",
      nullable: true,
      init: [],
      event: "changePricingunits"
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

    description: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeDescription"
    },

    isActive: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsActive"
    },
  },
});
