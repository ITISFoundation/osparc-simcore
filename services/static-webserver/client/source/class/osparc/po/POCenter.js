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
      padding: 10
    });

    const tabViews = this.__tabsView = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(osparc.desktop.credits.UserCenter.createMiniProfileView());

    const invitationsPage = this.__invitationsPage = this.__getInvitationsPage();
    tabViews.add(invitationsPage);

    this._add(tabViews);
  },

  members: {
    __tabsView: null,
    __invitationsPage: null,

    __getInvitationsPage: function() {
      const title = this.tr("Invitations");
      const iconSrc = "@FontAwesome5Solid/table/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const overview = new osparc.po.Invitations();
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

    openInvitations: function() {
      if (this.__invitationsPage) {
        this.__openPage(this.__invitationsPage);
      }
    }
  }
});
