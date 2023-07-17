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

qx.Class.define("osparc.component.resourceUsage.Summary", {
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
      this.__addSimulations(data.simulations);
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

    __addSimulations: function(simulations) {
      const simLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const title = new qx.ui.basic.Label().set({
        value: this.tr("Simulations remaining"),
        font: "text-13"
      });
      simLayout.add(title);

      const remaining = new qx.ui.basic.Label().set({
        value: `${simulations.total-simulations.used} of ${simulations.total} simulations`,
        font: "text-13"
      });
      simLayout.add(remaining);

      const progress = new qx.ui.indicator.ProgressBar().set({
        height: 8,
        maximum: simulations.total,
        value: simulations.total-simulations.used
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

      const topUpBtn = new qx.ui.form.Button().set({
        label: this.tr("Buy credits")
      });
      buttonsLayout.add(topUpBtn, {
        flex: 1
      });

      const detailedBtn = new qx.ui.form.Button().set({
        label: this.tr("Detailed view")
      });
      buttonsLayout.add(detailedBtn, {
        flex: 1
      });

      this._add(buttonsLayout);
    }
  }
});
