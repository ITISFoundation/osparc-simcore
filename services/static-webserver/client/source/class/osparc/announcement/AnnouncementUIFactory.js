/* ************************************************************************

  osparc - the simcore frontend

  https://osparc.io

  Copyright:
    2018 IT'IS Foundation, https://itis.swiss

  License:
    MIT: https://opensource.org/licenses/MIT

  Authors:
    * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.announcement.AnnouncementUIFactory", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    announcement: {
      check: "osparc.announcement.Announcement",
      init: null,
      nullable: false,
      event: "changeAnnouncement",
      apply: "__applyAnnouncement"
    }
  },

  statics: {
    createLoginAnnouncement: function(title, description) {
      const loginAnnouncement = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        backgroundColor: "strong-main",
        alignX: "center",
        padding: 12,
        allowGrowX: true,
        maxWidth: osparc.auth.core.BaseAuthPage.FORM_WIDTH,
        decorator: "rounded",
      });

      if (title) {
        const titleLabel = new qx.ui.basic.Label().set({
          value: title,
          font: "text-16",
          alignX: "center",
          textAlign: "center",
          rich: true
        });
        loginAnnouncement.add(titleLabel);
      }

      if (description) {
        const descriptionLabel = new qx.ui.basic.Label().set({
          value: description,
          font: "text-14",
          alignX: "center",
          textAlign: "center",
          rich: true
        });
        loginAnnouncement.add(descriptionLabel);
      }

      return loginAnnouncement;
    },

    isValid: function(announcement, widgetType) {
      if (announcement) {
        const now = new Date();
        const validPeriod = now > announcement.getStart() && now < announcement.getEnd();
        const validProduct = announcement.getProducts().includes(osparc.product.Utils.getProductName());
        const validWidgetType = widgetType ? announcement.getWidgets().includes(widgetType) : true;
        return validPeriod && validProduct && validWidgetType;
      }
      return false;
    },
  },

  members: {
    __announcements: null,
    __ribbonAnnouncement: null,

    setAnnouncementsData: function(announcementsData) {
      this.__announcements = [];
      announcementsData.forEach(announcementData => {
        const announcement = new osparc.announcement.Announcement(announcementData);
        this.__announcements.push(announcement);
      });
    },

    __applyAnnouncement: function() {
      if (this.__ribbonAnnouncement) {
        osparc.notification.RibbonNotifications.getInstance().removeNotification(this.__ribbonAnnouncement);
        this.__ribbonAnnouncement = null;
      }
      if (this.__hasRibbonAnnouncement()) {
        this.__addRibbonAnnouncement();
      }
    },

    hasLoginAnnouncement: function() {
      const announcement = this.getAnnouncement();
      return this.self().isValid(announcement, "login");
    },

    __hasRibbonAnnouncement: function() {
      const announcement = this.getAnnouncement();
      return this.self().isValid(announcement, "ribbon");
    },

    hasUserMenuAnnouncement: function() {
      const announcement = this.getAnnouncement();
      return this.self().isValid(announcement, "user-menu") && announcement.getLink();
    },

    createLoginAnnouncement: function() {
      const announcement = this.getAnnouncement();
      const loginAnnouncement = this.self().createLoginAnnouncement(announcement.getTitle(), announcement.getDescription());
      return loginAnnouncement;
    },

    __addRibbonAnnouncement: function() {
      const announcement = this.getAnnouncement();

      if (osparc.utils.Utils.localCache.isDontShowAnnouncement(announcement.getId())) {
        return;
      }

      let text = announcement.getTitle();
      if (announcement.getDescription()) {
        text += ": " + announcement.getDescription();
      }

      const ribbonAnnouncement = this.__ribbonAnnouncement = new osparc.notification.RibbonNotification(text, "announcement", true);
      ribbonAnnouncement.announcementId = announcement.getId();
      osparc.notification.RibbonNotifications.getInstance().addNotification(ribbonAnnouncement);
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
