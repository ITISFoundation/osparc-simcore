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
    this.__addRegisteredUsersPage();
    this.__addSearchUsersPage();
    this.__addPreRegistrationPage();
    this.__addInvitationsPage();
    this.__addProductPage();
    this.__addSendEmailPage();

    if (openPage) {
      this.__openPage(openPage);
    }
  },

  members: {
    __addReviewUsersPage: function() {
      const title = this.tr("Review Users");
      const iconSrc = "@FontAwesomeSolid/user-plus/22";
      const usersPending = new osparc.po.UsersPending();
      const page = this.addTab(title, iconSrc, usersPending);
      page.pageId = "reviewUsers";
    },

    __addRegisteredUsersPage: function() {
      const title = this.tr("Active Users");
      const iconSrc = "@MaterialIcons/how_to_reg/34";
      const usersRegistered = new osparc.po.UsersRegistered();
      this.addTab(title, iconSrc, usersRegistered);
    },

    __addSearchUsersPage: function() {
      const title = this.tr("Search Users");
      const iconSrc = "@FontAwesomeSolid/search/22";
      const users = new osparc.po.UsersSearch();
      this.addTab(title, iconSrc, users);
    },

    __addPreRegistrationPage: function() {
      const title = this.tr("Pre-Registration");
      const iconSrc = "@FontAwesomeSolid/address-card/22";
      const preRegistration = new osparc.po.PreRegistration();
      this.addTab(title, iconSrc, preRegistration);
    },

    __addInvitationsPage: function() {
      const title = this.tr("Invitations");
      const iconSrc = "@FontAwesomeSolid/envelope/22";
      const invitations = new osparc.po.Invitations();
      this.addTab(title, iconSrc, invitations);
    },

    __addProductPage: function() {
      const title = this.tr("Product Info");
      const iconSrc = "@FontAwesomeSolid/info/22";
      const productInfo = new osparc.po.ProductInfo();
      this.addTab(title, iconSrc, productInfo);
    },

    __addSendEmailPage: function() {
      const title = this.tr("Send Email");
      const iconSrc = "@FontAwesomeSolid/paper-plane/22";
      const sendEmail = new osparc.po.SendEmail();
      this.addTab(title, iconSrc, sendEmail);
    },

    __openPage: function(openPage) {
      const tabsView = this.getChildControl("tabs-view");
      const pages = tabsView.getChildren();
      const page = pages.find(pge => pge.pageId && pge.pageId === openPage);
      if (page) {
        tabsView.setSelection([page]);
      }
    },
  }
});
