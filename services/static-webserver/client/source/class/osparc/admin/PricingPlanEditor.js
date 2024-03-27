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

qx.Class.define("osparc.admin.PricingPlanEditor", {
  extend: qx.ui.core.Widget,

  construct: function(pricingPlan) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const ppKey = this.getChildControl("pp-key");
    const name = this.getChildControl("name");
    this.getChildControl("description");
    this.getChildControl("classification");

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    ppKey.setRequired(true);
    name.setRequired(true);
    manager.add(name);

    pricingPlan ? this.getChildControl("create") : this.getChildControl("save");
  },

  properties: {
    ppKey: {
      check: "Number",
      init: 0,
      nullable: false,
      event: "changePpKey"
    },

    name: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeName"
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
    }
  },

  events: {
    "createPricingPlan": "qx.event.type.Event",
    "updatePricingPlan": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pp-key": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Pricing Plan Key")
          });
          this.bind("ppKey", control, "value");
          control.bind("value", this, "ppKey");
          this._add(control);
          break;
        }
        case "name": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Name")
          });
          this.bind("name", control, "name");
          control.bind("value", this, "name");
          this._add(control);
          break;
        }
        case "description": {
          control = new qx.ui.form.TextArea().set({
            font: "text-14",
            placeholder: this.tr("Description")
          });
          this.bind("description", control, "value");
          control.bind("value", this, "description");
          this._add(control);
          break;
        }
        case "classification": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            readOnly: true
          });
          this.bind("classification", control, "value");
          control.bind("value", this, "classification");
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
              this.fireEvent("createPricingPlan");
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
              this.fireEvent("updatePricingPlan");
            }
          }, this);
          buttons.addAt(control, 1);
          break;
        }
      }

      return control || this.base(arguments, id);
    }
  }
});
