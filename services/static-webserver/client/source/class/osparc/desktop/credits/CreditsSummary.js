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

    this._setLayout(new qx.ui.layout.Grow());

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
    WIDTH: 200
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
    }
  }
});
