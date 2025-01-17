/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.Usage", {
  extend: osparc.desktop.credits.ResourceInTableViewer,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "table": {
          const dateFilters = this.getChildControl("date-filters");
          control = new osparc.desktop.credits.UsageTable(this._getSelectWalletId(), dateFilters.getValue()).set({
            marginTop: 10
          });
          const fetchingImage = this.getChildControl("fetching-image");
          control.getTableModel().bind("isFetching", fetchingImage, "visibility", {
            converter: isFetching => isFetching ? "visible" : "excluded"
          })
          this._add(control, { flex: 1 })
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _handleExport: function() {
      const reportUrl = new URL("/v0/services/-/usage-report", window.location.origin);
      reportUrl.searchParams.append("wallet_id", this._getSelectWalletId());
      const dateFilters = this.getChildControl("date-filters");
      reportUrl.searchParams.append("filters", JSON.stringify({ "started_at": dateFilters.getValue() }));
      window.open(reportUrl, "_blank");
    },
  }
});
