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

qx.Class.define("osparc.desktop.credits.Transactions", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    const transactionsTable = this.getChildControl("transactions-table");
    osparc.data.Resources.fetch("payments", "get")
      .then(transactions => {
        if ("data" in transactions) {
          transactionsTable.addData(transactions["data"]);
        }
      })
      .catch(err => console.error(err));
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "transactions-table":
          control = new osparc.desktop.credits.TransactionsTable();
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __fetchData: function() {
      osparc.data.Resources.fetch("payments", "get")
        .then(transactions => {
          if ("data" in transactions) {
            const table = this.getChildControl("usage-table");
            table.addData(transactions["data"]);
          }
        })
        .catch(err => console.error(err));
    }
  }
});
