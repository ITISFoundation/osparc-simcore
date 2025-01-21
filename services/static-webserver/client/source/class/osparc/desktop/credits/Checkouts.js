/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.desktop.credits.Checkouts", {
  extend: osparc.desktop.credits.ResourceInTableViewer,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "table": {
          const dateFilters = this.getChildControl("date-filters");
          control = new osparc.desktop.credits.CheckoutsTable(this._getSelectWalletId(), dateFilters.getValue()).set({
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

    _buildLayout: function() {
      this.base(arguments);

      this.getChildControl("export-button").exclude();
    },
  }
});
