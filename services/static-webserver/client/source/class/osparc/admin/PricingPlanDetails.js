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

qx.Class.define("osparc.admin.PricingPlanDetails", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.getChildControl("back-to-pp-button");
    this.getChildControl("pricing-plan-details");
    this.getChildControl("pricing-units");
  },

  events: {
    "backToPricingPlans": "qx.event.type.Event"
  },

  members: {
    __pricingPlanModel: null,
    __pricingPlanListItem: null,
    __pricingUnitsList: null,
    __servicesList: null,

    _createChildControlImpl: function(id) {
      let control;
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
          control = new osparc.admin.PricingPlanListItem();
          this.getChildControl("title-layout").add(control, {
            flex: 1
          });
          break;
        case "tab-view":
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 10
          });
          this._addAt(control, 1, {
            flex: 1
          });
          break;
        case "pricing-units": {
          control = this.__createTabPage(this.tr("Pricing Units"), "@FontAwesome5Solid/users/14");
          const pricingUnitsList = this.__pricingUnitsList = new osparc.admin.PricingUnitsList();
          control.add(pricingUnitsList, {
            flex: 1
          });
          this.getChildControl("tab-view").add(control);
        }
      }
      return control || this.base(arguments, id);
    },

    setCurrentPricingPlan: function(pricingPlanModel) {
      if (pricingPlanModel === null) {
        return;
      }
      this.__pricingPlanModel = pricingPlanModel;

      const pricingPlanListItem = this.getChildControl("pricing-plan-details");
      pricingPlanModel.bind("model", pricingPlanListItem, "model");
      pricingPlanModel.bind("ppId", pricingPlanListItem, "ppId");
      pricingPlanModel.bind("ppKey", pricingPlanListItem, "ppKey");
      pricingPlanModel.bind("title", pricingPlanListItem, "title");
      pricingPlanModel.bind("description", pricingPlanListItem, "description");
      pricingPlanModel.bind("isActive", pricingPlanListItem, "isActive");

      // set PricingPlanId to the tab views
      this.__pricingUnitsList.setPricingPlanId(pricingPlanModel.getModel());
      // this.__servicesList.setPricingPlanId(pricingPlanModel.getModel());
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
    },

    __getTabs: function() {
      const tabView = new qx.ui.tabview.TabView().set({
        contentPadding: 10
      });
      tabView.getChildControl("pane");


      /*
      const servicesListPage = this.__createTabPage(this.tr("Services"), "@FontAwesome5Solid/cogs/14");
      const servicesList = this.__servicesList = new osparc.desktop.organizations.ServicesList();
      servicesListPage.add(servicesList, {
        flex: 1
      });
      tabView.add(servicesListPage);
      */

      return tabView;
    }
  }
});
