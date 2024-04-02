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
      costPerUnit: unitData.currentCostPerUnit,
      specificInfo: unitData.specificInfo && unitData.specificInfo["aws_ec2_instances"] ? unitData.specificInfo["aws_ec2_instances"].toString() : "",
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
  },

  members: {
    serialize: function() {
      const serialized = {
        unitName: this.getUnitName(),
        currentCostPerUnit: this.getCurrentCostPerUnit(),
        specificInfo: {
          "aws_ec2_instances": [this.getAwsSpecificInfo()]
        },
        extraInfo: this.getUnitExtraInfo(),
        default: this.getDefault()
      };
      if (this.getPricingUnitId()) {
        serialized.pricingUnitId = this.getPricingUnitId()
      }
      return serialized;
    }
  }
});
