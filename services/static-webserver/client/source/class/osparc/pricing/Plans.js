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

qx.Class.define("osparc.pricing.Plans", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("pricing-plans-filter");
    this.__createList();
    this.fetchPlans();
    this.getChildControl("create-pricing-plan");
  },

  events: {
    "pricingPlanSelected": "qx.event.type.Data"
  },

  members: {
    __model: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pricing-plans-filter":
          control = new osparc.filter.TextFilter("text", "pricingPlansList").set({
            allowStretchX: true,
            margin: 0
          });
          this._addAt(control, 0);
          break;
        case "pricing-plans-container":
          control = new qx.ui.container.Scroll();
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "pricing-plans-list":
          control = new qx.ui.form.List().set({
            decorator: "no-border",
            spacing: 3
          });
          control.addListener("changeSelection", e => {
            const selection = e.getData();
            if (selection.length) {
              const ppSelected = selection[0];
              this.fireDataEvent("pricingPlanSelected", ppSelected);
            }
          }, this);
          this.getChildControl("pricing-plans-container").add(control);
          break;
        case "create-pricing-plan":
          control = new qx.ui.form.Button().set({
            appearance: "form-button",
            label: this.tr("New Pricing Plan"),
            alignX: "center",
            icon: "@FontAwesome5Solid/plus/14",
            allowGrowX: false
          });
          control.addListener("execute", () => this.__openCreatePricingPlan());
          this._addAt(control, 2);
      }
      return control || this.base(arguments, id);
    },

    __createList: function() {
      const list = this.getChildControl("pricing-plans-list");

      const model = this.__model = new qx.data.Array();
      const ppsCtrl = new qx.data.controller.List(model, list, "label");
      ppsCtrl.setDelegate({
        createItem: () => new osparc.pricing.PlanListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("pricingPlanId", "model", null, item, id);
          ctrl.bindProperty("pricingPlanId", "ppId", null, item, id);
          ctrl.bindProperty("pricingPlanKey", "ppKey", null, item, id);
          ctrl.bindProperty("name", "title", null, item, id);
          ctrl.bindProperty("description", "description", null, item, id);
          ctrl.bindProperty("classification", "classification", null, item, id);
          ctrl.bindProperty("isActive", "isActive", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("pricingPlansList");
          item.addListener("editPricingPlan", () => this.__openUpdatePricingPlan(item.getModel()));
        }
      });
    },

    fetchPlans: function() {
      osparc.store.Pricing.getInstance().fetchPricingPlans()
        .then(data => this.__populateList(data));
    },

    __populateList: function(pricingPlans) {
      this.__model.removeAll();
      pricingPlans.forEach(pricingPlan => this.__model.append(pricingPlan));
    },

    __openCreatePricingPlan: function() {
      const ppCreator = new osparc.pricing.PlanEditor();
      const title = this.tr("Pricing Plan Creator");
      const win = osparc.ui.window.Window.popUpInWindow(ppCreator, title, 400, 250);
      ppCreator.addListener("done", () => {
        win.close();
        this.fetchPlans();
      });
      ppCreator.addListener("cancel", () => win.close());
    },

    __openUpdatePricingPlan: function(pricingPlanId) {
      osparc.store.Pricing.getInstance().fetchPricingUnits(pricingPlanId)
        .then(pricingPlan => {
          const ppEditor = new osparc.pricing.PlanEditor(pricingPlan);
          const title = this.tr("Pricing Plan Editor");
          const win = osparc.ui.window.Window.popUpInWindow(ppEditor, title, 400, 250);
          ppEditor.addListener("done", () => {
            win.close();
            this.fetchPlans();
          });
          ppEditor.addListener("cancel", () => win.close());
        });
    }
  }
});
