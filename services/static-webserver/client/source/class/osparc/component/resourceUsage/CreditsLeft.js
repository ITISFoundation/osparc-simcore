/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.resourceUsage.CreditsLeft", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    osparc.data.Resources.dummy.getCreditsLeft()
      .then(data => this.__buildLayout(data))
      .catch(err => console.error(err));
  },

  members: {
    __buildLayout: function(data) {
      this.__addCredits(data.credits);
    },

    __addCredits: function(credits) {
      const store = osparc.store.Store.getInstance();
      store.setCredits(credits.left);

      const progress = new qx.ui.indicator.ProgressBar().set({
        maximum: 1,
        maxHeight: 20,
        maxWidth: 50,
        alignY:"middle",
        cursor: "pointer"
      });
      const logBase = (n, base) => Math.log(n) / Math.log(base);
      store.bind("credits", progress, "value", {
        converter: val => {
          let normalized = logBase(val, 10000) + 0.01;
          normalized = Math.min(Math.max(normalized, 0), 1);
          return normalized;
        }
      });
      progress.bind("value", progress.getChildControl("progress"), "backgroundColor", {
        converter: val => {
          if (val > 0.4) {
            return "strong-main";
          } else if (val > 0.1) {
            return "warning-yellow";
          }
          return "danger-red";
        }
      });
      store.bind("credits", progress, "toolTipText", {
        converter: val => val + "credits left"
      });

      progress.addListener("tap", () => {
        const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
        creditsWindow.openBuyCredits();
      }, this);

      this._add(progress);
    },

    __addButtons: function() {
      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const buyCreditsBtn = new qx.ui.form.Button().set({
        label: this.tr("Buy credits")
      });
      buttonsLayout.add(buyCreditsBtn, {
        flex: 1
      });

      const usageOverviewBtn = new qx.ui.form.Button().set({
        label: this.tr("Detailed")
      });
      usageOverviewBtn.addListener("execute", () => {
        const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
        creditsWindow.openUsageOverview();
      }, this);

      buttonsLayout.add(usageOverviewBtn, {
        flex: 1
      });

      this._add(buttonsLayout);
    }
  }
});
