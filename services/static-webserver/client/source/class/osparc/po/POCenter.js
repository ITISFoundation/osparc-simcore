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
    const miniProfile = osparc.desktop.credits.MyAccount.createMiniProfileView().set({
      paddingRight: 10
    });
    tabViews.getChildControl("bar").add(miniProfile);

    const usersPage = this.__getUsersPage();
    tabViews.add(usersPage);

    const preRegistration = this.__getPreRegistrationPage();
    tabViews.add(preRegistration);

    const invitationsPage = this.__getInvitationsPage();
    tabViews.add(invitationsPage);

    const productPage = this.__getProductPage();
    tabViews.add(productPage);

    const msgTemplatesPage = this.__getMsgTemplatesPage();
    tabViews.add(msgTemplatesPage);

    this._add(tabViews, {
      flex: 1
    });
  },

  members: {
    __widgetToPage: function(title, iconSrc, widget) {
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      widget.set({
        margin: 10
      });
      page.add(widget, {
        flex: 1
      });
      return page;
    },

    __getUsersPage: function() {
      const title = this.tr("Users");
      const iconSrc = "@FontAwesome5Solid/user/22";
      const users = new osparc.po.Users();
      const page = this.__widgetToPage(title, iconSrc, users)
      return page;
    },

    __getPreRegistrationPage: function() {
      const title = this.tr("PreRegistration");
      const iconSrc = "@FontAwesome5Solid/address-card/22";
      const page = new osparc.desktop.preferences.pages.BasePage(title, iconSrc);
      const preRegistration = new osparc.po.PreRegistration();
      preRegistration.set({
        margin: 10
      });
      page.add(preRegistration);
      return page;
    },

    __getInvitationsPage: function() {
      const title = this.tr("Invitations");
      const iconSrc = "@FontAwesome5Solid/envelope/22";
      const invitations = new osparc.po.Invitations();
      const page = this.__widgetToPage(title, iconSrc, invitations);
      return page;
    },

    __getProductPage: function() {
      const title = this.tr("Product Info");
      const iconSrc = "@FontAwesome5Solid/info/22";
      const productInfo = new osparc.po.ProductInfo();
      const page = this.__widgetToPage(title, iconSrc, productInfo);
      return page;
    },

    __getMsgTemplatesPage: function() {
      const title = this.tr("Message Templates");
      const iconSrc = "@FontAwesome5Solid/envelope-open/22";
      const productInfo = new osparc.po.MessageTemplates();
      const page = this.__widgetToPage(title, iconSrc, productInfo);
      return page;
    }
  }
});
