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

    this.__createList();
    this.__fetchPricingUnits();
    this.getChildControl("create-pricing-unit");
  },

  members: {
    __model: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pricing-units-container":
          control = new qx.ui.container.Scroll();
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "pricing-units-list":
          control = new qx.ui.form.List().set({
            decorator: "no-border",
            spacing: 3
          });
          this.getChildControl("pricing-units-container").add(control);
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
          this._addAt(control, 2);
      }
      return control || this.base(arguments, id);
    },

    __createList: function() {
      const list = this.getChildControl("pricing-units-list");

      const model = this.__model = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(model, list, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.admin.PricingUnitListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("pricingUnitId", "model", null, item, id);
          ctrl.bindProperty("pricingUnitId", "ppId", null, item, id);
          ctrl.bindProperty("pricingUnitKey", "ppKey", null, item, id);
          ctrl.bindProperty("displayName", "title", null, item, id);
          ctrl.bindProperty("description", "description", null, item, id);
          ctrl.bindProperty("isActive", "isActive", null, item, id);
        },
        configureItem: item => {
          item.addListener("editPricingUnit", () => this.__updatePricingUnit(item.getModel()));
        }
      });
    },

    __fetchUnits: function() {
      const params = {
        url: {
          pricingPlan: 1
        }
      }
      osparc.data.Resources.fetch("pricingUnits", "get", params)
        .then(data => this.__populateList(data));
    },

    __populateList: function(pricingUnits) {
      this.__model.removeAll();
      pricingUnits.forEach(pricingUnit => this.__model.append(qx.data.marshal.Json.createModel(pricingUnit)));
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
