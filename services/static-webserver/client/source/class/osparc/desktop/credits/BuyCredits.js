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

    this._setLayout(new qx.ui.layout.VBox(20));

    this.__nCredits = 1;

    this.__buildLayout();
  },

  members: {
    __nCredits: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "credit-offers-view":
          control = this.__getCreditOffersView();
          this._add(control);
          break;
        case "credit-selector":
          control = this.__getCreditSelector();
          this._add(control);
          break;
        case "summary-view":
          control = this.__getSummaryView();
          this._add(control);
          break;
        case "buy-button":
          control = this.__getBuyButton();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("credit-offers-view");
      this.getChildControl("credit-selector");
      this.getChildControl("summary-view");
      this.getChildControl("buy-button");
    },

    __getCreditOffersView: function() {
      const grid = new qx.ui.layout.Grid(15, 10);
      grid.setColumnAlign(0, "right", "middle");
      const layout = new qx.ui.container.Composite(grid);

      let row = 0;
      const creditsTitle = new qx.ui.basic.Label(this.tr("Credits")).set({
        font: "text-16"
      });
      layout.add(creditsTitle, {
        row,
        column: 0
      });

      const pricePerCreditTitle = new qx.ui.basic.Label(this.tr("Credit price")).set({
        font: "text-16"
      });
      layout.add(pricePerCreditTitle, {
        row,
        column: 1
      });
      row++;

      [
        [1, 5],
        [10, 4],
        [100, 3],
        [1000, 2]
      ].forEach(pair => {
        const creditsLabel = new qx.ui.basic.Label().set({
          value: pair[0].toString(),
          font: "text-14"
        });
        layout.add(creditsLabel, {
          row,
          column: 0
        });

        const pricePerCreditLabel = new qx.ui.basic.Label().set({
          value: pair[1] + " $",
          font: "text-14"
        });
        layout.add(pricePerCreditLabel, {
          row,
          column: 1
        });

        row++;
      });
      return layout;
    },

    __getCreditSelector: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(0));

      const minBtn = new qx.ui.form.Button().set({
        label: this.tr("-"),
        width: 25
      });
      layout.add(minBtn);

      const nCreditsField = new qx.ui.form.TextField().set({
        value: this.__nCredits.toString(),
        width: 100,
        textAlign: "center",
        font: "text-14"
      });
      layout.add(nCreditsField);

      const updateCredits = () => {
        nCreditsField.setValue(this.__nCredits.toString());
      };

      const moreBtn = new qx.ui.form.Button().set({
        label: this.tr("+"),
        width: 25
      });
      layout.add(moreBtn);

      minBtn.addListener("execute", () => {
        this.__nCredits--;
        updateCredits();
      });
      moreBtn.addListener("execute", () => {
        this.__nCredits++;
        updateCredits();
      });

      return layout;
    },

    __getSummaryView: function() {
      const grid = new qx.ui.layout.Grid(15, 10);
      grid.setColumnAlign(0, "right", "middle");
      const layout = new qx.ui.container.Composite(grid);

      const label1 = new qx.ui.basic.Label().set({
        value: "Total price",
        font: "text-16"
      });
      layout.add(label1, {
        row: 0,
        column: 0
      });

      const label2 = new qx.ui.basic.Label().set({
        value: "Credit price",
        font: "text-14"
      });
      layout.add(label2, {
        row: 1,
        column: 0
      });

      const label3 = new qx.ui.basic.Label().set({
        value: "Saving",
        font: "text-14"
      });
      layout.add(label3, {
        row: 2,
        column: 0
      });

      const label4 = new qx.ui.basic.Label().set({
        value: "VAT 7%",
        font: "text-14"
      });
      layout.add(label4, {
        row: 3,
        column: 0
      });

      return layout;
    },

    __getBuyButton: function() {
      const buyBtn = new qx.ui.form.Button().set({
        label: this.tr("Buy credits"),
        font: "text-16",
        appearance: "strong-button",
        maxWidth: 150,
        center: true
      });
      return buyBtn;
    }
  }
});
