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

qx.Class.define("osparc.admin.PricingUnitsList", {
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
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
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
      const params = {
        url: {
          pricingPlanId: this.getPricingPlanId()
        }
      };
      osparc.data.Resources.fetch("pricingPlans", "getOne", params)
        .then(data => this.__populateList(data["pricingUnits"]));
    },

    __populateList: function(pricingUnits) {
      this.getChildControl("pricing-units-container").removeAll();

      if (pricingUnits === null) {
        return;
      }

      pricingUnits.forEach(pricingUnit => {
        const pUnit = new osparc.study.PricingUnit(pricingUnit).set({
          advanced: true,
          showSpecificInfo: true,
          allowGrowY: false
        });
        this.getChildControl("pricing-units-container").add(pUnit);
      });
    },

    __openCreatePricingUnit: function() {
      const ppCreator = new osparc.admin.PricingUnitEditor();
      const title = this.tr("Pricing Unit Creator");
      const win = osparc.ui.window.Window.popUpInWindow(ppCreator, title, 400, 250);
      ppCreator.addListener("done", () => {
        win.close();
        this.__fetchUnits();
      });
      ppCreator.addListener("cancel", () => win.close());
    },

    __updatePricingUnit: function(pricingUnitId) {
      const params = {
        url: {
          pricingPlanId: pricingUnitId
        }
      }
      osparc.data.Resources.fetch("pricingUnits", "getOne", params)
        .then(pricingUnit => {
          const ppEditor = new osparc.admin.PricingUnitEditor(pricingUnit);
          const title = this.tr("Pricing Unit Editor");
          const win = osparc.ui.window.Window.popUpInWindow(ppEditor, title, 400, 250);
          ppEditor.addListener("done", () => {
            win.close();
            this.__fetchUnits();
          });
          ppEditor.addListener("cancel", () => win.close());
        });
    }
  }
});
