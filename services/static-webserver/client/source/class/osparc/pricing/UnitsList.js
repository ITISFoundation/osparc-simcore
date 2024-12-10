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

qx.Class.define("osparc.pricing.UnitsList", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("pricing-units-container");
    this.getChildControl("create-pricing-unit");
  },

  properties: {
    pricingPlanId: {
      check: "Number",
      init: null,
      nullable: false,
      apply: "__fetchUnits"
    }
  },

  members: {
    __model: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pricing-units-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._addAt(control, 0, {
            flex: 1
          });
          break;
        case "create-pricing-unit":
          control = new qx.ui.form.Button().set({
            appearance: "form-button",
            label: this.tr("New Pricing Unit"),
            alignX: "center",
            icon: "@FontAwesome5Solid/plus/14",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__openCreatePricingUnit());
          this._addAt(control, 1);
      }
      return control || this.base(arguments, id);
    },

    __fetchUnits: function() {
      osparc.store.Pricing.getInstance().fetchPricingUnits(this.getPricingPlanId())
        .then(pricingUnits => this.__populateList(pricingUnits));
    },

    __populateList: function(pricingUnits) {
      this.getChildControl("pricing-units-container").removeAll();

      if (pricingUnits === null) {
        return;
      }

      pricingUnits.forEach(pricingUnit => {
        let pUnit = null;
        if (pricingUnit.getClassification() === "LICENSE") {
          pUnit = new osparc.study.PricingUnitLicense(pricingUnit).set({
            showRentButton: false,
          });
        } else {
          pUnit = new osparc.study.PricingUnitTier(pricingUnit).set({
            showAwsSpecificInfo: true,
          });
        }
        pUnit.set({
          showEditButton: true,
        });
        pUnit.addListener("editPricingUnit", () => this.__openUpdatePricingUnit(pricingUnit));
        this.getChildControl("pricing-units-container").add(pUnit);
      });

      const buttons = this.getChildControl("pricing-units-container").getChildren();
      const keepDefaultSelected = () => {
        buttons.forEach(btn => {
          btn.setSelected(btn.getUnitData().getIsDefault());
        });
      };
      keepDefaultSelected();
      buttons.forEach(btn => btn.addListener("execute", () => keepDefaultSelected()));
    },

    __openCreatePricingUnit: function() {
      const puCreator = new osparc.pricing.UnitEditor().set({
        pricingPlanId: this.getPricingPlanId()
      });
      const title = this.tr("Pricing Unit Creator");
      const win = osparc.ui.window.Window.popUpInWindow(puCreator, title, 400, 250);
      puCreator.addListener("done", () => {
        win.close();
        this.__fetchUnits();
      });
      puCreator.addListener("cancel", () => win.close());
    },

    __openUpdatePricingUnit: function(pricingUnit) {
      const puEditor = new osparc.pricing.UnitEditor(pricingUnit).set({
        pricingPlanId: this.getPricingPlanId()
      });
      const title = this.tr("Pricing Unit Editor");
      const win = osparc.ui.window.Window.popUpInWindow(puEditor, title, 400, 250);
      puEditor.addListener("done", () => {
        win.close();
        this.__fetchUnits();
      });
      puEditor.addListener("cancel", () => win.close());
    }
  }
});
