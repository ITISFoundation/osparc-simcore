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

    const ppKey = this.getChildControl("pp-key");
    const name = this.getChildControl("name");
    this.getChildControl("description");
    this.getChildControl("classification");
    const isActive = this.getChildControl("is-active");

    const manager = this.__validator = new qx.ui.form.validation.Manager();
    ppKey.setRequired(true);
    name.setRequired(true);
    manager.add(ppKey);
    manager.add(name);

    if (pricingUnit) {
      this.__pricingUnit = osparc.utils.Utils.deepCloneObject(pricingUnit);
      this.set({
        ppKey: pricingUnit.pricingUnitKey,
        name: pricingUnit.displayName,
        description: pricingUnit.description,
        classification: pricingUnit.classification,
        isActive: pricingUnit.isActive
      });
      ppKey.setEnabled(false);
      this.getChildControl("save");
    } else {
      isActive.setEnabled(false);
      this.getChildControl("create");
    }
  },

  properties: {
    ppKey: {
      check: "String",
      init: "",
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
    },

    isActive: {
      check: "Boolean",
      init: true,
      nullable: false,
      event: "changeIsActive"
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
        case "pp-key": {
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            placeholder: this.tr("Pricing Unit Key")
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
          this.bind("name", control, "value");
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
            enabled: false
          });
          this.bind("classification", control, "value");
          control.bind("value", this, "classification");
          this._add(control);
          break;
        }
        case "is-active": {
          control = new qx.ui.form.CheckBox().set({
            value: true
          });
          this.bind("isActive", control, "value");
          control.bind("value", this, "isActive");
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
      const ppKey = this.getPpKey();
      const name = this.getName();
      const description = this.getDescription();
      const classification = this.getClassification();
      const params = {
        data: {
          "pricingUnitKey": ppKey,
          "displayName": name,
          "description": description,
          "classification": classification
        }
      };
      osparc.data.Resources.fetch("pricingUnits", "post", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          this.fireEvent("done");
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          console.error(err);
        })
        .finally(() => this.getChildControl("create").setFetching(false));
    },

    __updatePricingUnit: function() {
      this.__pricingUnit["displayName"] = this.getName();
      this.__pricingUnit["description"] = this.getDescription();
      this.__pricingUnit["isActive"] = this.getIsActive();
      const params = {
        url: {
          "pricingUnitId": this.__pricingUnit["pricingUnitId"]
        },
        data: this.__pricingUnit
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
