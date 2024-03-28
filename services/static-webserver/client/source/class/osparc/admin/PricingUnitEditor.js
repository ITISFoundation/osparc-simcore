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

qx.Class.define("osparc.admin.PricingUnitEditor", {
  extend: qx.ui.core.Widget,

  construct: function(pricingUnit) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const unitName = this.getChildControl("unit-name");
    const costPerUnit = this.getChildControl("cost-per-unit");
    this.getChildControl("comment");
    const specificInfo = this.getChildControl("specific-info");
    const unitExtraInfo = this.getChildControl("unit-extra-info");
    const isDefault = this.getChildControl("is-default");

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    unitName.setRequired(true);
    costPerUnit.setRequired(true);
    specificInfo.setRequired(true);
    unitExtraInfo.setRequired(true);
    isDefault.setRequired(true);
    manager.add(unitName);
    manager.add(costPerUnit);
    manager.add(specificInfo);
    manager.add(unitExtraInfo);
    manager.add(isDefault);

    if (pricingUnit) {
      this.__pricingUnit = osparc.utils.Utils.deepCloneObject(pricingUnit);
      this.set({
        unitName: pricingUnit.unitName,
        costPerUnit: pricingUnit.costPerUnit,
        comment: pricingUnit.comment,
        specificInfo: pricingUnit.specificInfo,
        unitExtraInfo: pricingUnit.unitExtraInfo,
        default: pricingUnit.default
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
      init: "",
      nullable: false,
      event: "changeSpecificInfo"
    },

    unitExtraInfo: {
      check: "String",
      init: "{}",
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
    __pricingUnit: null,
    __validator: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "unit-name":
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Unit Name")
          });
          this.bind("unitName", control, "value");
          control.bind("value", this, "unitName");
          this._add(control);
          break;
        case "cost-per-unit":
          control = new qx.ui.form.Spinner().set({
            minimum: 0,
            maximum: 10000
          });
          this.bind("costPerUnit", control, "value");
          control.bind("value", this, "costPerUnit");
          this._add(control);
          break;
        case "comment":
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Comment")
          });
          this.bind("comment", control, "value");
          control.bind("value", this, "comment");
          this._add(control);
          break;
        case "specific-info": {
          control = new qx.ui.form.TextArea().set({
            font: "text-14",
            placeholder: this.tr("aws_ec2_instances")
          });
          this.bind("specificInfo", control, "value");
          control.bind("value", this, "specificInfo");
          this._add(control);
          break;
        }
        case "unit-extra-info": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("{}")
          });
          this.bind("unitExtraInfo", control, "value");
          control.bind("value", this, "unitExtraInfo");
          this._add(control);
          break;
        }
        case "is-default": {
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          this.bind("default", control, "value");
          control.bind("value", this, "default");
          this._add(control);
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
      const extraInfo = this.getExtraInfo();
      const isDefault = this.getIsDefault();
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
      const extraInfo = this.getExtraInfo();
      const isDefault = this.getIsDefault();
      const params = {
        url: {
          "pricingPlanId": this.getPricingPlanId(),
          "pricingUnitId": this.__pricingUnit["pricingUnitId"]
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
