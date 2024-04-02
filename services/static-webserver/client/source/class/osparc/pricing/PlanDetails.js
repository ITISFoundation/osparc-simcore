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

qx.Class.define("osparc.pricing.PlanDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-to-pp-button");
    this.getChildControl("pricing-plan-details");
    this.getChildControl("pricing-units");
    this.getChildControl("service-list");
  },

  events: {
    "backToPricingPlans": "qx.event.type.Event"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      let layout;
      switch (id) {
        case "title-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._addAt(control, 0);
          break;
        case "back-to-pp-button":
          control = new qx.ui.form.Button().set({
            toolTipText: this.tr("Back to Pricing Plans"),
            icon: "@FontAwesome5Solid/arrow-left/20",
            backgroundColor: "transparent"
          });
          control.addListener("execute", () => this.fireEvent("backToPricingPlans"));
          this.getChildControl("title-layout").add(control);
          break;
        case "pricing-plan-details":
          control = new osparc.pricing.PlanListItem();
          control.getChildControl("edit-button").exclude();
          this.getChildControl("title-layout").add(control, {
            flex: 1
          });
          break;
        case "resources-view":
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 10
          });
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "pricing-units": {
          control = new osparc.pricing.UnitsList();
          const tabPage = this.__createTabPage(this.tr("Pricing Units"), "@FontAwesome5Solid/paw/14");
          tabPage.add(control, {
            flex: 1
          });
          layout = this.getChildControl("resources-view");
          layout.add(tabPage);
          break;
        }
        case "service-list": {
          control = new osparc.pricing.ServicesList();
          const tabPage = this.__createTabPage(this.tr("Services"), "@FontAwesome5Solid/cogs/14");
          tabPage.add(control, {
            flex: 1
          });
          layout = this.getChildControl("resources-view");
          layout.add(tabPage);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    setCurrentPricingPlan: function(pricingPlanModel) {
      if (pricingPlanModel === null) {
        return;
      }

      const pricingPlanListItem = this.getChildControl("pricing-plan-details");
      pricingPlanModel.bind("model", pricingPlanListItem, "model");
      pricingPlanModel.bind("ppId", pricingPlanListItem, "ppId");
      pricingPlanModel.bind("ppKey", pricingPlanListItem, "ppKey");
      pricingPlanModel.bind("title", pricingPlanListItem, "title");
      pricingPlanModel.bind("description", pricingPlanListItem, "description");
      pricingPlanModel.bind("isActive", pricingPlanListItem, "isActive");

      // set PricingPlanId to the tab views
      this.getChildControl("pricing-units").setPricingPlanId(pricingPlanModel.getModel());
      this.getChildControl("service-list").setPricingPlanId(pricingPlanModel.getModel());
    },

    __createTabPage: function(label, icon) {
      const tabPage = new qx.ui.tabview.Page().set({
        layout: new qx.ui.layout.VBox()
      });
      if (label) {
        tabPage.setLabel(label);
      }
      if (icon) {
        tabPage.setIcon(icon);
      }
      tabPage.getChildControl("button").set({
        font: "text-13"
      });
      return tabPage;
    }
  }
});
