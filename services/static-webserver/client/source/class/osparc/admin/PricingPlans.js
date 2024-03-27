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
          control.addListener("changeSelection", e => console.log(e.getData()), this);
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

    _buildLayout: function() {
      this.getChildControl("pricing-plans-filter");
      osparc.data.Resources.fetch("pricingPlans", "get")
        .then(data => this.__populateList(data));
      this.getChildControl("create-pricing-plan");
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
    },

    __openCreatePricingPlan: function() {
      const ppCreator = new osparc.admin.PricingPlanEditor();
      const title = this.tr("Pricing Plan Creator");
      const win = osparc.ui.window.Window.popUpInWindow(ppCreator, title, 400, 250);
      ppCreator.addListener("createPricingPlan", () => {
        this.__createPricingPlan(win, ppCreator.getChildControl("create"), ppCreator)
        console.log(ppCreator);
      });
      ppCreator.addListener("cancel", () => win.close());
    },

    __updatePricingPlan: function(pricingPlan) {
      const ppEditor = new osparc.admin.PricingPlanEditor(pricingPlan);
      const title = this.tr("Pricing Plan Editor");
      const win = osparc.ui.window.Window.popUpInWindow(ppEditor, title, 400, 250);
      ppEditor.addListener("updatePricingPlan", () => {
        console.log(ppEditor);
      });
      ppEditor.addListener("cancel", () => win.close());
    },

    __createPricingPlan: function(win, button, ppCreator) {
      const ppKey = ppCreator.getPpKey();
      const name = ppCreator.getName();
      const description = ppCreator.getDescription();
      const classification = ppCreator.getClassification();
      const params = {
        data: {
          "pricingPlanKey": ppKey,
          "displayName": name,
          "description": description,
          "classification": classification
        }
      };
      osparc.data.Resources.fetch("pricingPlans", "post", params)
        .then(() => {
          osparc.FlashMessenger.getInstance().logAs(name + this.tr(" successfully created"));
          button.setFetching(false);
        })
        .catch(err => {
          osparc.FlashMessenger.getInstance().logAs(this.tr("Something went wrong creating ") + name, "ERROR");
          button.setFetching(false);
          console.error(err);
        })
        .finally(() => win.close());
    },
  }
});
