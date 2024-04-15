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

  construct: function() {
    this.base(arguments);

    const miniProfile = osparc.desktop.account.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniProfile);

    this.__addUsersPage();
    this.__addPreRegistrationPage();
    this.__addInvitationsPage();
    this.__addProductPage();
    this.__addMsgTemplatesPage();
  },

  members: {
    __addUsersPage: function() {
      const title = this.tr("Users");
      const iconSrc = "@FontAwesome5Solid/user/22";
      const users = new osparc.po.Users();
      this.addTab(title, iconSrc, users);
    },

    __addPreRegistrationPage: function() {
      const title = this.tr("PreRegistration");
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

    __addMsgTemplatesPage: function() {
      const title = this.tr("Message Templates");
      const iconSrc = "@FontAwesome5Solid/envelope-open/22";
      const productInfo = new osparc.po.MessageTemplates();
      this.addTab(title, iconSrc, productInfo);
    }
  }
});
