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

qx.Class.define("osparc.admin.PricingPlans", {
  extend: osparc.po.BaseView,

  members: {
    __model: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pricing-plans-filter":
          control = new osparc.filter.TextFilter("text", "pricingPlansList").set({
            allowStretchX: true,
            margin: [0, 10, 5, 10]
          });
          this._add(control);
          break;
        case "pricing-plans-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
        case "pricing-plans-list":
          control = new qx.ui.form.List().set({
            decorator: "no-border",
            spacing: 3
          });
          control.addListener("changeSelection", e => console.log(e.getData()), this);
          this.getChildControl("pricing-plans-container").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("pricing-plans-filter");
      osparc.data.Resources.fetch("pricingPlans", "get")
        .then(data => this.__populateList(data));
    },

    __populateList: function(pricingPlans) {
      if (pricingPlans.length === 0) {
        return;
      }

      const list = this.getChildControl("pricing-plans-list");

      const model = this.__model = new qx.data.Array();
      const orgsCtrl = new qx.data.controller.List(model, list, "label");
      orgsCtrl.setDelegate({
        createItem: () => new osparc.admin.PricingPlanListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("pricingPlanId", "model", null, item, id);
          ctrl.bindProperty("pricingPlanId", "ppId", null, item, id);
          ctrl.bindProperty("pricingPlanKey", "ppKey", null, item, id);
          ctrl.bindProperty("displayName", "title", null, item, id);
          ctrl.bindProperty("description", "description", null, item, id);
          ctrl.bindProperty("isActive", "isActive", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("pricingPlansList");
        }
      });

      pricingPlans.forEach(pricingPlan => model.append(qx.data.marshal.Json.createModel(pricingPlan)));
    }
  }
});
