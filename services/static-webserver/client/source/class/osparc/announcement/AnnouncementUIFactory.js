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

  events: {
    "changeAnnouncements": "qx.event.type.Event",
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
    __ribbonAnnouncements: null,

    setAnnouncementsData: function(announcementsData) {
      this.__announcements = [];
      announcementsData.forEach(announcementData => {
        const announcement = new osparc.announcement.Announcement(announcementData);
        this.__announcements.push(announcement);
      });
      this.fireEvent("changeAnnouncements");

      this.__addToRibbon();
    },

    __addToRibbon: function() {
      if (this.__ribbonAnnouncements && this.__ribbonAnnouncements.length) {
        this.__ribbonAnnouncements.forEach(ribbonAnnouncement => {
          osparc.notification.RibbonNotifications.getInstance().removeNotification(ribbonAnnouncement);
        });
      }
      this.__ribbonAnnouncements = [];
      this.__announcements.forEach(announcement => {
        if (this.self().isValid(announcement, "ribbon")) {
          const ribbonAnnouncement = this.__addRibbonAnnouncement(announcement);
          if (ribbonAnnouncement) {
            this.__ribbonAnnouncements.push(ribbonAnnouncement);
          }
        }
      });
    },

    hasLoginAnnouncement: function() {
      return this.__announcements && this.__announcements.some(announcement => this.self().isValid(announcement, "login"));
    },

    hasUserMenuAnnouncement: function() {
      return this.__announcements && this.__announcements.some(announcement => this.self().isValid(announcement, "ribbon") && announcement.getLink());
    },

    createLoginAnnouncements: function() {
      const loginAnnouncements = [];
      this.__announcements.forEach(announcement => {
        if (this.self().isValid(announcement, "login")) {
          const loginAnnouncement = this.self().createLoginAnnouncement(announcement.getTitle(), announcement.getDescription())
          loginAnnouncement.setWidth(osparc.auth.core.BaseAuthPage.FORM_WIDTH-5); // show 1-2 pixel of the nearby announcement
          loginAnnouncements.push(loginAnnouncement);
        }
      });
      if (loginAnnouncements.length === 1) {
        return loginAnnouncements[0];
      }
      const slideBar = new osparc.widget.SlideBar().set({
        allowGrowX: true,
      });
      slideBar.getChildControl("button-backward").set({
        backgroundColor: "transparent"
      });
      slideBar.getChildControl("button-forward").set({
        backgroundColor: "transparent"
      });
      loginAnnouncements.forEach(loginAnnouncement => slideBar.add(loginAnnouncement));
      return slideBar;
    },

    __addRibbonAnnouncement: function(announcement) {
      if (osparc.utils.Utils.localCache.isDontShowAnnouncement(announcement.getId())) {
        return null;
      }

      let text = "";
      if (announcement.getTitle()) {
        text += announcement.getTitle();
      }
      if (announcement.getTitle() && announcement.getDescription()) {
        text += ": ";
      }
      if (announcement.getDescription()) {
        text += announcement.getDescription();
      }
      const ribbonAnnouncement = new osparc.notification.RibbonNotification(text, "announcement", true);
      ribbonAnnouncement.announcementId = announcement.getId();
      osparc.notification.RibbonNotifications.getInstance().addNotification(ribbonAnnouncement);
      return ribbonAnnouncement;
    },

    createUserMenuAnnouncements: function() {
      const userMenuAnnouncements = [];
      this.__announcements.forEach(announcement => {
        if (this.self().isValid(announcement, "user-menu")) {
          const link = announcement.getLink();
          const userMenuAnnouncement = new qx.ui.menu.Button(announcement.getTitle() + "...");
          userMenuAnnouncement.addListener("execute", () => window.open(link));
          userMenuAnnouncements.push(userMenuAnnouncement);
        }
      });
      return userMenuAnnouncements;
    }
  }
});
