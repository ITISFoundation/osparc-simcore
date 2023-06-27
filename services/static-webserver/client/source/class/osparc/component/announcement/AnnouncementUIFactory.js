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

  construct: function(announcement) {
    this.base(arguments);

    if (announcement) {
      this.setAnnouncement(announcement);
    }
  },

  properties: {
    announcement: {
      check: "osparc.component.announcement.Announcement",
      init: null,
      nullable: false
    }
  },

  members: {
    __loginAnnouncement: null,
    __userMenuAnnouncement: null,

    buildAnnouncementUIs: function() {
      console.log("build announcements", this.getAnnouncement());
      this.__buildLoginAnnouncement();
      this.__buildUserMenuAnnouncement();
    },

    getLoginAnnouncement: function() {
      if (this.__isValid() && this.__loginAnnouncement) {
        return this.__loginAnnouncement;
      }
      return null;
    },

    getUserMenuAnnouncement: function() {
      if (this.__isValid() && this.__userMenuAnnouncement) {
        return this.__userMenuAnnouncement;
      }
      return null;
    },

    __isValid: function() {
      const announcement = this.getAnnouncement();

      const now = new Date();
      if (
        announcement.getStart() &&
        announcement.getEnd() &&
        now > announcement.getStart() &&
        now < announcement.getEnd()
      ) {
        return true;
      }
      return false;
    },

    __buildLoginAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const announcmentLayout = this.__loginAnnouncement = new qx.ui.container.Composite(new qx.ui.layout.VBox(5)).set({
        backgroundColor: "strong-main",
        alignX: "center",
        padding: 12,
        allowGrowX: true,
        maxWidth: 300
      });
      announcmentLayout.getContentElement().setStyles({
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
      announcmentLayout.add(titleLabel);

      const descriptionLabel = new qx.ui.basic.Label().set({
        value: announcement.getDescription(),
        font: "text-14",
        textColor: "white",
        alignX: "center",
        rich: true,
        wrap: true
      });
      announcmentLayout.add(descriptionLabel);
    },

    __buildUserMenuAnnouncement: function() {
      const announcement = this.getAnnouncement();

      const link = announcement.getLink();
      if (link) {
        const button = this.__userMenuAnnouncement = new qx.ui.menu.Button(announcement.getTitle() + "...");
        button.addListener("execute", () => window.open(link));
      }
    }
  }
});
