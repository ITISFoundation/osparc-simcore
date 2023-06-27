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

qx.Class.define("osparc.component.announcement.AnnouncementUIFactory", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    announcement: {
      check: "osparc.component.announcement.Announcement",
      init: null,
      nullable: false,
      apply: "__applyAnnouncement"
    }
  },

  members: {
    __isValid: function(widgetType) {
      const announcement = this.getAnnouncement();

      const now = new Date();
      if (
        announcement.getProducts().includes(osparc.product.Utils.getProductName()) &&
        announcement.getWidgets().includes(widgetType) &&
        now > announcement.getStart() &&
        now < announcement.getEnd()
      ) {
        return true;
      }
      return false;
    },

    __applyAnnouncement: function() {
      if (this.hasRibbonAnnouncement()) {
        this.addRibbonAnnouncement();
      }
    },

    hasLoginAnnouncement: function() {
      return this.__isValid("login");
    },

    hasRibbonAnnouncement: function() {
      return this.__isValid("ribbon");
    },

    hasUserMenuAnnouncement: function() {
      return this.__isValid("user-menu") && this.getAnnouncement().getLink();
    },

    createLoginAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const loginAnnouncement = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        backgroundColor: "strong-main",
        alignX: "center",
        padding: 12,
        allowGrowX: true,
        maxWidth: 300
      });
      loginAnnouncement.getContentElement().setStyles({
        "border-radius": "8px"
      });

      const titleLabel = new qx.ui.basic.Label().set({
        value: announcement.getTitle(),
        font: "text-16",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      loginAnnouncement.add(titleLabel);

      const descriptionLabel = new qx.ui.basic.Label().set({
        value: announcement.getDescription(),
        font: "text-14",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      loginAnnouncement.add(descriptionLabel);

      return loginAnnouncement;
    },

    addRibbonAnnouncement: function() {
      const announcement = this.getAnnouncement();
      let text = announcement.getTitle() + ": ";
      text += announcement.getDescription();

      const ribbonNotification = new osparc.component.notification.RibbonNotification(text, "announcement", true);
      osparc.component.notification.RibbonNotifications.getInstance().addNotification(ribbonNotification);
    },

    createUserMenuAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const link = announcement.getLink();
      const userMenuAnnouncement = new qx.ui.menu.Button(announcement.getTitle() + "...");
      userMenuAnnouncement.addListener("execute", () => window.open(link));
      return userMenuAnnouncement;
    }
  }
});
