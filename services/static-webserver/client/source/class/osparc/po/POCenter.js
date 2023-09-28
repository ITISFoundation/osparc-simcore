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

qx.Class.define("osparc.po.POCenter", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      padding: 20,
      paddingLeft: 10
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(osparc.desktop.credits.UserCenter.createMiniProfileView());

    const operationsPage = this.__operationsPage = this.__getOperationsPage();
    tabViews.add(operationsPage);

    this._add(tabViews);
  },

  members: {
    __tabsView: null,
    __operationsPage: null,

    __getOperationsPage: function() {
      const title = this.tr("Operations");
      const iconSrc = "@FontAwesome5Solid/table/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const overview = new osparc.po.Overview();
      overview.set({
        margin: 10
      });
      page.add(overview);
      return page;
    },

    __openPage: function(page) {
      if (page) {
        this.__tabsView.setSelection([page]);
      }
    },

    openOperations: function() {
      if (this.__operationsPage) {
        this.__openPage(this.__operationsPage);
      }
    }
  }
});
