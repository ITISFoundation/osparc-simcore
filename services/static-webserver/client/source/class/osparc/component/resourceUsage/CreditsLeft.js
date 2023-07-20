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

    this._setLayout(new qx.ui.layout.VBox(12));

    osparc.data.Resources.dummy.getUsageOverview()
      .then(data => this.__buildLayout(data))
      .catch(err => console.error(err));
  },

  members: {
    __buildLayout: function(data) {
      this.__addTitle();
      this.__addCredits(data.simulations);
      this.__addComputing(data.computing);
      this.__addButtons();
    },

    __addTitle: function() {
      const title = new qx.ui.basic.Label().set({
        value: "Usage Overview",
        font: "text-14"
      });
      this._add(title);
    },

    __addCredits: function(simulations) {
      const simLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const title = new qx.ui.basic.Label().set({
        value: this.tr("Credits remaining"),
        font: "text-13"
      });
      simLayout.add(title);

      const store = osparc.store.Store.getInstance();
      store.setCredits(simulations.total);
      const remaining = new qx.ui.basic.Label().set({
        font: "text-13"
      });
      store.bind("credits", remaining, "value", {
        converter: val => `${val-simulations.used} of ${val} credits`
      });
      simLayout.add(remaining);

      const progress = new qx.ui.indicator.ProgressBar().set({
        height: 8
      });
      store.bind("credits", progress, "maximum");
      store.bind("credits", progress, "value", {
        converter: val => val-simulations.used
      });
      progress.getChildControl("progress").set({
        backgroundColor: "strong-main"
      });
      simLayout.add(progress);

      this._add(simLayout);
    },

    __addComputing: function(computing) {
      const compLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const title = new qx.ui.basic.Label().set({
        value: this.tr("Computational hours remaining"),
        font: "text-13"
      });
      compLayout.add(title);

      const compTotal = Math.round(computing.total/(60*60*1000));
      const compUsed = Math.round(computing.used/(60*60*1000));
      const remaining = new qx.ui.basic.Label().set({
        value: `${compTotal-compUsed} of ${compTotal} CPU hours`,
        font: "text-13"
      });
      compLayout.add(remaining);

      const progress = new qx.ui.indicator.ProgressBar().set({
        height: 8,
        maximum: computing.total,
        value: computing.total-computing.used
      });
      progress.getChildControl("progress").set({
        backgroundColor: "strong-main"
      });
      compLayout.add(progress);

      this._add(compLayout);
    },

    __addButtons: function() {
      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const buyCreditsBtn = new qx.ui.form.Button().set({
        label: this.tr("Buy credits")
      });
      buyCreditsBtn.addListener("execute", () => {
        const creditsWindow = osparc.desktop.credits.CreditsWindow.openWindow();
        creditsWindow.openBuyCredits();
      }, this);
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
