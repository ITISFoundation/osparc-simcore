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
  extend: osparc.ui.window.TabbedView,

  construct: function(openPage) {
    this.base(arguments);

    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetToTabs(miniProfile);

    this.__addReviewUsersPage();
    this.__addActiveUsersPage();
    this.__addPreRegistrationPage();
    this.__addInvitationsPage();
    this.__addProductPage();

    if (openPage) {
      this.__openPage(openPage);
    }
  },

  members: {
    __addReviewUsersPage: function() {
      const title = this.tr("Review Users");
      const iconSrc = "@FontAwesome5Solid/user-plus/22";
      const usersPending = new osparc.po.UsersPending();
      const page = this.addTab(title, iconSrc, usersPending);
      page.pageId = "reviewUsers";
    },

    __addActiveUsersPage: function() {
      const title = this.tr("Active Users");
      const iconSrc = "@FontAwesome5Solid/user/22";
      const users = new osparc.po.Users();
      this.addTab(title, iconSrc, users);
    },

    __addPreRegistrationPage: function() {
      const title = this.tr("Pre-Registration");
      const iconSrc = "@FontAwesome5Solid/address-card/22";
      const preRegistration = new osparc.po.PreRegistration();
      this.addTab(title, iconSrc, preRegistration);
    },

    __addInvitationsPage: function() {
      const title = this.tr("Invitations");
      const iconSrc = "@FontAwesome5Solid/envelope/22";
      const invitations = new osparc.po.Invitations();
      this.addTab(title, iconSrc, invitations);
    },

    __addProductPage: function() {
      const title = this.tr("Product Info");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const productInfo = new osparc.po.ProductInfo();
      this.addTab(title, iconSrc, productInfo);
    },

    __openPage: function(openPage) {
      const tabsView = this.getChildControl("tabs-view");
      const pages = tabsView.getChildren();
      const page = pages.find(page => page.pageId && page.pageId === openPage);
      if (page) {
        tabsView.setSelection([page]);
      }
    },
  }
});
