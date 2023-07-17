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

qx.Class.define("osparc.desktop.credits.BuyCredits", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.__buildLayout();
  },

  members: {
    __prevRequestParams: null,
    __nextRequestParams: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credit-offers-view":
          control = this.__getCreditOffersView();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("credit-offers-view");
    },

    __getCreditOffersView: function() {
      const grid = new qx.ui.layout.Grid(10, 10);
      const layout = new qx.ui.container.Composite(grid);
      this._add(layout);

      const creditsTitle = new qx.ui.basic.Label(this.tr("Credits")).set({
        font: "text-16"
      });
      layout.add(creditsTitle, {
        row: 0,
        colum: 0
      });

      const pricePerCreditTitle = new qx.ui.basic.Label(this.tr("Price/Credit")).set({
        font: "text-16"
      });
      layout.add(pricePerCreditTitle, {
        row: 0,
        colum: 1
      });

      [
        [10, 1],
        [100, 0.8],
        [1000, 0.7]
      ].forEach((pair, idx) => {
        const creditsLabel = new qx.ui.basic.Label(pair[0]).set({
          font: "text-14"
        });
        layout.add(creditsLabel, {
          row: idx,
          colum: 0
        });

        const pricePerCreditLabel = new qx.ui.basic.Label(pair[1]).set({
          font: "text-14"
        });
        layout.add(pricePerCreditLabel, {
          row: idx,
          colum: 0
        });
      });
    }
  }
});
