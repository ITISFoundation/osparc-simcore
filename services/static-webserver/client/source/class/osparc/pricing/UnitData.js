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
 * Class that stores Pricing Unit data.
 *
 */

qx.Class.define("osparc.pricing.UnitData", {
  extend: qx.core.Object,

  construct: function(unitData) {
    this.base(arguments);

    this.set({
      pricingUnitId: unitData.pricingUnitId ? unitData.pricingUnitId : null,
      unitName: unitData.unitName,
      currentCostPerUnit: parseFloat(unitData.currentCostPerUnit),
      comment: unitData.comment ? unitData.comment : "",
      awsSpecificInfo: unitData.specificInfo && unitData.specificInfo["aws_ec2_instances"] ? unitData.specificInfo["aws_ec2_instances"].toString() : "",
      unitExtraInfo: unitData.unitExtraInfo,
      default: unitData.default
    });
  },

  properties: {
    pricingUnitId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changePricingUnitId"
    },

    unitName: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeUnitName"
    },

    currentCostPerUnit: {
      check: "Number",
      nullable: false,
      init: 0,
      event: "changeCurrentCostPerUnit"
    },

    comment: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeComment"
    },

    awsSpecificInfo: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeAwsSpecificInfo"
    },

    unitExtraInfo: {
      check: "Object",
      init: {},
      nullable: false,
      event: "changeUnitExtraInfo"
    },

    default: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeDefault"
    }
  }
});
