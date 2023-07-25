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

qx.Class.define("osparc.desktop.credits.CreditsLeft", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout();
  },

  statics: {
    createCreditsLeftInidcator: function(supportTap = false) {
      const store = osparc.store.Store.getInstance();

      const progressBar = new qx.ui.indicator.ProgressBar().set({
        maximum: 1,
        width: 50,
        height: 20,
        allowGrowY: false,
        alignY:"middle"
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

      if (supportTap) {
        progressBar.set({
          cursor: "pointer"
        });
        progressBar.addListener("tap", () => {
          const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
          creditsWindow.openBuyCredits();
        }, this);
      }

      return progressBar;
    }
  },

  members: {
    __buildLayout: function() {
      this.__addCredits();
    },

    __addCredits: function() {
      const progressBar = this.self().createCreditsLeftInidcator(true);
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
