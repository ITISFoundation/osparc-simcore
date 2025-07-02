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

qx.Class.define("osparc.desktop.credits.CreditsSummary", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.set({
      appearance: "floating-menu",
      padding: 8,
      maxWidth: this.self().WIDTH,
      minHeight: 150,
      zIndex: osparc.utils.Utils.FLOATING_Z_INDEX,
    });
    osparc.utils.Utils.setIdToWidget(this, "creditsSummary");

    this.__buildLayout();

    const root = qx.core.Init.getApplication().getRoot();
    root.add(this, {
      top: 0,
      right: 0
    });
  },

  statics: {
    BILLING_CENTER_BUTTON_SIZE: 26,
    WIDTH: 350,
    TIME_RANGES: [{
      key: 1,
      label: "Last 24h"
    }, {
      key: 7,
      label: "Last week"
    }, {
      key: 30,
      label: "Last month"
    }]
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "top-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control);
          break;
        case "top-left-spacer": {
          const buttonSize = this.self().BILLING_CENTER_BUTTON_SIZE;
          control = new qx.ui.core.Spacer(buttonSize, buttonSize);
          const topLayout = this.getChildControl("top-layout");
          topLayout.add(control);
          break;
        }
        case "credits-indicator": {
          control = new osparc.desktop.credits.CreditsIndicator();
          control.getChildControl("credits-bar").exclude();
          const store = osparc.store.Store.getInstance();
          store.bind("contextWallet", control, "wallet");
          const topLayout = this.getChildControl("top-layout");
          topLayout.add(control, {
            flex: 1
          });
          break;
        }
        case "billing-center-button": {
          const buttonSize = this.self().BILLING_CENTER_BUTTON_SIZE;
          control = new qx.ui.form.Button().set({
            appearance: "form-button-outlined",
            width: buttonSize,
            height: buttonSize,
            alignX: "center",
            alignY: "middle",
            center: true,
            icon: "@FontAwesome5Solid/ellipsis-v/12"
          });
          // make it circular
          control.getContentElement().setStyles({
            "border-radius": `${buttonSize / 2}px`
          });
          control.addListener("execute", () => {
            osparc.desktop.credits.BillingCenterWindow.openWindow();
            this.exclude();
          });
          osparc.utils.Utils.setIdToWidget(control, "billingCenterButton");
          const topLayout = this.getChildControl("top-layout");
          topLayout.add(control);
          break;
        }
        case "time-range-sb": {
          control = new qx.ui.form.SelectBox().set({
            allowGrowX: false,
            alignX: "center",
            backgroundColor: "transparent"
          });
          this.self().TIME_RANGES.forEach(tr => {
            const trItem = new qx.ui.form.ListItem(tr.label, null, tr.key);
            control.add(trItem);
          });
          // default one week
          const found = control.getSelectables().find(trItem => trItem.getModel() === 7);
          if (found) {
            control.setSelection([found]);
          }
          this._add(control);
          break;
        }
        case "services-consumption":
          control = new osparc.desktop.credits.CreditsPerService();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    setPosition: function(x, y) {
      this.setLayoutProperties({
        left: x - this.self().WIDTH,
        top: y
      });
    },

    __buildLayout: function() {
      this.getChildControl("top-left-spacer");
      this.getChildControl("credits-indicator");
      this.getChildControl("billing-center-button");
      this.__buildConsumptionSummary();
    },

    __buildConsumptionSummary: function() {
      const timeRangeSB = this.getChildControl("time-range-sb");
      const servicesConsumption = this.getChildControl("services-consumption");

      const fetchData = () => {
        const selection = timeRangeSB.getSelection();
        if (selection.length) {
          servicesConsumption.setDaysRange(selection[0].getModel());
        }
      };

      fetchData();
      timeRangeSB.addListener("changeSelection", () => fetchData(), this);
    }
  }
});
