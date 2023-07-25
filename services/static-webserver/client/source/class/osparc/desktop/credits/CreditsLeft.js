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

    this._setLayout(new qx.ui.layout.VBox(3));

    this.set({
      padding: 4
    });

    this.__buildLayout();
  },

  statics: {
    createCreditsLeftInidcator: function(wallet, supportTap = false) {
      const progressBar = new qx.ui.indicator.ProgressBar().set({
        maximum: 1,
        width: 50,
        maxHeight: 20,
        allowGrowY: false,
        alignY:"middle"
      });

      const logBase = (n, base) => Math.log(n) / Math.log(base);
      wallet.bind("credits", progressBar, "value", {
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
      wallet.bind("credits", progressBar, "toolTipText", {
        converter: val => wallet.getLabel() + ": " + val + " credits left"
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
      const store = osparc.store.Store.getInstance();
      store.getWallets().forEach(wallet => {
        const progressBar = this.self().createCreditsLeftInidcator(wallet, true).set({
          allowShrinkY: true
        });
        this._add(progressBar, {
          flex: 1
        });
      });
    }
  }
});
