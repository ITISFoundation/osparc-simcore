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

  statics: {
    createCreditsLeftInidcator: function() {
      const store = osparc.store.Store.getInstance();

      const progressBar = new qx.ui.indicator.ProgressBar().set({
        maximum: 1,
        width: 50,
        height: 20,
        allowGrowY: false,
        alignY:"middle",
        cursor: "pointer"
      });
      const logBase = (n, base) => Math.log(n) / Math.log(base);
      store.bind("credits", progressBar, "value", {
        converter: val => {
          let normalized = logBase(val, 10000) + 0.01;
          normalized = Math.min(Math.max(normalized, 0), 1);
          return normalized;
        }
      });
      progressBar.bind("value", progressBar.getChildControl("progress"), "backgroundColor", {
        converter: val => {
          if (val > 0.4) {
            return "strong-main";
          } else if (val > 0.1) {
            return "warning-yellow";
          }
          return "danger-red";
        }
      });
      store.bind("credits", progressBar, "toolTipText", {
        converter: val => val + " credits left"
      });
      return progressBar;
    }
  },

  members: {
    __buildLayout: function(data) {
      this.__addCredits(data.credits);
    },

    __addCredits: function(credits) {
      const store = osparc.store.Store.getInstance();
      store.setCredits(credits.left);

      const progressBar = this.self().createCreditsLeftInidcator();
      progressBar.addListener("tap", () => {
        const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
        creditsWindow.openBuyCredits();
      }, this);

      this._add(progressBar);
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
