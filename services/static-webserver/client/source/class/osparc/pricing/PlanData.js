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
 * Class that stores Pricing Plan data.
 *
 */

qx.Class.define("osparc.pricing.PlanData", {
  extend: qx.core.Object,

  construct: function(planData) {
    this.base(arguments);

    this.set({
      pricingPlanId: planData.pricingPlanId,
      pricingPlanKey: planData.pricingPlanKey,
      displayName: planData.displayName,
      description: planData.description,
      classification: planData.classification,
      isActive: planData.isActive
    });
  },

  properties: {
    pricingPlanId: {
      check: "Number",
      nullable: false,
      init: 0,
      event: "changePricingPlanId"
    },

    pricingPlanKey: {
      check: "String",
      nullable: false,
      init: "",
      event: "changePricingPlanKey"
    },

    displayName: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDisplayName"
    },

    description: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeDescription"
    },

    classification: {
      check: "String",
      init: "TIER",
      nullable: false,
      event: "changeClassification"
    },

    isActive: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeIsActive"
    },

    pricingUnits: {
      check: "Array",
      init: [],
      nullable: false,
      event: "changePricingUnits"
    }
  }
});
