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
      maxWidth: this.self().WIDTH
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
    WIDTH: 200,
    TIME_RANGES: [{
      key: 1,
      label: "Today"
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
        case "credits-indicator": {
          control = new osparc.desktop.credits.CreditsIndicator();
          if (osparc.utils.Utils.isDevelopmentPlatform()) {
            control.getChildControl("credits-bar").exclude();
          }
          const store = osparc.store.Store.getInstance();
          store.bind("contextWallet", control, "wallet");
          const topLayout = this.getChildControl("top-layout");
          topLayout.add(control, {
            flex: 1
          });
          break;
        }
        case "billing-center-button": {
          const buttonSize = 26;
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
          control = new qx.ui.form.SelectBox();
          this.self().TIME_RANGES.forEach(tr => {
            const trItem = new qx.ui.form.ListItem(tr.label, null, tr.key);
            control.add(trItem);
          });
          this._add(control);
        }
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
      this.getChildControl("credits-indicator");
      this.getChildControl("billing-center-button");
      if (osparc.utils.Utils.isDevelopmentPlatform()) {
        this.__buildConsumptionSummary();
      }
    },

    __buildConsumptionSummary: function() {
      this.getChildControl("time-range-sb");
    }
  }
});
