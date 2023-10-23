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

    const tabViews = new qx.ui.tabview.TabView().set({
      barPosition: "left",
      contentPadding: 0
    });
    tabViews.getChildControl("bar").add(osparc.desktop.credits.UserCenter.createMiniProfileView());

    const invitationsPage = this.__getInvitationsPage();
    tabViews.add(invitationsPage);

    const productPage = this.__getProductPage();
    tabViews.add(productPage);

    this._add(tabViews);
  },

  members: {
    __getInvitationsPage: function() {
      const title = this.tr("Invitations");
      const iconSrc = "@FontAwesome5Solid/envelope/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const invitations = new osparc.po.Invitations();
      invitations.set({
        margin: 10
      });
      page.add(invitations);
      return page;
    },

    __getProductPage: function() {
      const title = this.tr("Product Info");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      page.showLabelOnTab();
      const productInfo = new osparc.po.ProductInfo();
      productInfo.set({
        margin: 10
      });
      page.add(productInfo);
      return page;
    }
  }
});
