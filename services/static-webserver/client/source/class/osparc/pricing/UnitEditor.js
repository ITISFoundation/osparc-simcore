/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.pricing.UnitEditor", {
  extend: qx.ui.core.Widget,

  construct: function(pricingUnitData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const unitName = this.getChildControl("unit-name");
    const costPerUnit = this.getChildControl("cost-per-unit");
    this.getChildControl("comment");
    const specificInfo = this.getChildControl("specific-info");
    const unitExtraInfoCPU = this.getChildControl("unit-extra-info-cpu");
    const unitExtraInfoRAM = this.getChildControl("unit-extra-info-ram");
    const unitExtraInfoVRAM = this.getChildControl("unit-extra-info-vram");
    const unitExtraInfo = this.getChildControl("unit-extra-info");
    this.getChildControl("is-default");

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    unitName.setRequired(true);
    costPerUnit.setRequired(true);
    specificInfo.setRequired(true);
    unitExtraInfoCPU.setRequired(true);
    unitExtraInfoRAM.setRequired(true);
    unitExtraInfoVRAM.setRequired(true);
    unitExtraInfo.setRequired(true);
    manager.add(unitName);
    manager.add(costPerUnit);
    manager.add(specificInfo);
    manager.add(unitExtraInfo);

    if (pricingUnitData) {
      this.set({
        pricingUnitId: pricingUnitData.pricingUnitId,
        unitName: pricingUnitData.unitName,
        costPerUnit: parseFloat(pricingUnitData.currentCostPerUnit),
        comment: pricingUnitData.comment ? pricingUnitData.comment : "",
        specificInfo: pricingUnitData.specificInfo && pricingUnitData.specificInfo["aws_ec2_instances"] ? pricingUnitData.specificInfo["aws_ec2_instances"].toString() : "",
        default: pricingUnitData.default
      });
      const extraInfo = osparc.utils.Utils.deepCloneObject(pricingUnitData.unitExtraInfo);
      // extract the required fields from the unitExtraInfo
      this.set({
        unitExtraInfoCPU: extraInfo["CPU"],
        unitExtraInfoRAM: extraInfo["RAM"],
        unitExtraInfoVRAM: extraInfo["VRAM"]
      });
      delete extraInfo["CPU"];
      delete extraInfo["RAM"];
      delete extraInfo["VRAM"];
      this.set({
        unitExtraInfo: extraInfo
      });
      this.getChildControl("save");
    } else {
      this.getChildControl("create");
    }
  },

  properties: {
    pricingPlanId: {
      check: "Number",
      init: null,
      nullable: false,
    },

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

    costPerUnit: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeCostPerUnit"
    },

    comment: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeComment"
    },

    specificInfo: {
      check: "String",
      init: "t2.medium",
      nullable: false,
      event: "changeSpecificInfo"
    },

    unitExtraInfoCPU: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeUnitExtraInfoCPU"
    },

    unitExtraInfoRAM: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeUnitExtraInfoRAM"
    },

    unitExtraInfoVRAM: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changeUnitExtraInfoVRAM"
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

  events: {
    "done": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __validator: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "unit-form": {
          control = new qx.ui.form.Form();
          const formRenderer = new qx.ui.form.renderer.Single(control);
          this._add(formRenderer);
          break;
        }
        case "unit-name":
          control = new qx.ui.form.TextField().set({
            font: "text-14"
          });
          this.bind("unitName", control, "value");
          control.bind("value", this, "unitName");
          this.getChildControl("unit-form").add(control, this.tr("Unit Name"));
          break;
        case "cost-per-unit":
          control = new qx.ui.form.Spinner().set({
            minimum: 0,
            maximum: 10000
          });
          this.bind("costPerUnit", control, "value");
          control.bind("value", this, "costPerUnit");
          this.getChildControl("unit-form").add(control, this.tr("Cost per unit"));
          break;
        case "comment":
          control = new qx.ui.form.TextField().set({
            font: "text-14"
          });
          this.bind("comment", control, "value");
          control.bind("value", this, "comment");
          this.getChildControl("unit-form").add(control, this.tr("Comment"));
          break;
        case "specific-info": {
          control = new qx.ui.form.TextArea().set({
            font: "text-14"
          });
          this.bind("specificInfo", control, "value");
          control.bind("value", this, "specificInfo");
          this.getChildControl("unit-form").add(control, this.tr("Specific info"));
          break;
        }
        case "unit-extra-info-cpu": {
          control = new qx.ui.form.Spinner().set({
            minimum: 0,
            maximum: 10000
          });
          this.bind("unitExtraInfoCPU", control, "value");
          control.bind("value", this, "unitExtraInfoCPU");
          this.getChildControl("unit-form").add(control, this.tr("CPU"));
          break;
        }
        case "unit-extra-info-ram": {
          control = new qx.ui.form.Spinner().set({
            minimum: 0,
            maximum: 10000
          });
          this.bind("unitExtraInfoRAM", control, "value");
          control.bind("value", this, "unitExtraInfoRAM");
          this.getChildControl("unit-form").add(control, this.tr("RAM"));
          break;
        }
        case "unit-extra-info-vram": {
          control = new qx.ui.form.Spinner().set({
            minimum: 0,
            maximum: 10000
          });
          this.bind("unitExtraInfoVRAM", control, "value");
          control.bind("value", this, "unitExtraInfoVRAM");
          this.getChildControl("unit-form").add(control, this.tr("VRAM"));
          break;
        }
        case "unit-extra-info": {
          control = new qx.ui.form.TextField().set({
            font: "text-14"
          });
          this.bind("unitExtraInfo", control, "value", {
            converter: v => JSON.stringify(v)
          });
          control.bind("value", this, "unitExtraInfo", {
            converter: v => JSON.parse(v)
          });
          this.getChildControl("unit-form").add(control, this.tr("More Extra Info"));
          break;
        }
        case "is-default": {
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          this.bind("default", control, "value");
          control.bind("value", this, "default");
          this.getChildControl("unit-form").add(control, this.tr("Default"));
          break;
        }
        case "buttonsLayout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignX: "right"
          }));
          const cancelButton = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text"
          });
          cancelButton.addListener("execute", () => this.fireEvent("cancel"), this);
          control.addAt(cancelButton, 0);
          this._add(control);
          break;
        }
        case "create": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Create")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.__createPricingUnit();
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
        case "save": {
          const buttons = this.getChildControl("buttonsLayout");
          control = new osparc.ui.form.FetchButton(this.tr("Save")).set({
            appearance: "form-button"
          });
          control.addListener("execute", () => {
            if (this.__validator.validate()) {
              control.setFetching(true);
              this.__updatePricingUnit();
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __createPricingUnit: function() {
      const unitName = this.getUnitName();
      const costPerUnit = this.getCostPerUnit();
      const comment = this.getComment();
      const specificInfo = this.getSpecificInfo();
      const extraInfo = {};
      extraInfo["CPU"] = this.getUnitExtraInfoCPU();
      extraInfo["RAM"] = this.getUnitExtraInfoRAM();
      extraInfo["VRAM"] = this.getUnitExtraInfoVRAM();
      Object.assign(extraInfo, this.getUnitExtraInfo());
      const isDefault = this.getDefault();
      const params = {
        url: {
          "pricingPlanId": this.getPricingPlanId()
        },
        data: {
          "unitName": unitName,
          "costPerUnit": costPerUnit,
          "comment": comment,
          "specificInfo": {
            "aws_ec2_instances": [specificInfo]
          },
          "unitExtraInfo": extraInfo,
          "default": isDefault
        }
      };
      osparc.data.Resources.fetch("pricingUnits", "post", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Successfully created"));
          this.fireEvent("done");
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong"), "ERROR");
          console.error(err);
        })
        .finally(() => this.getChildControl("create").setFetching(false));
    },

    __updatePricingUnit: function() {
      const unitName = this.getUnitName();
      const costPerUnit = this.getCostPerUnit();
      const comment = this.getComment();
      const specificInfo = this.getSpecificInfo();
      const extraInfo = {};
      extraInfo["CPU"] = this.getUnitExtraInfoCPU();
      extraInfo["RAM"] = this.getUnitExtraInfoRAM();
      extraInfo["VRAM"] = this.getUnitExtraInfoVRAM();
      Object.assign(extraInfo, this.getUnitExtraInfo());
      const isDefault = this.getDefault();

      const params = {
        url: {
          "pricingPlanId": this.getPricingPlanId(),
          "pricingUnitId": this.getPricingUnitId()
        },
        data: {
          "unitName": unitName,
          "pricingUnitCostUpdate": {
            "cost_per_unit": costPerUnit,
            "comment": comment
          },
          "specificInfo": {
            "aws_ec2_instances": [specificInfo]
          },
          "unitExtraInfo": extraInfo,
          "default": isDefault
        }
      };
      osparc.data.Resources.fetch("pricingUnits", "update", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Successfully updated"));
          this.fireEvent("done");
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong"), "ERROR");
          console.error(err);
        })
        .finally(() => this.getChildControl("save").setFetching(false));
    }
  }
});
