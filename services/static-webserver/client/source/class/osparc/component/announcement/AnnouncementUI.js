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
      nullable: false,
      apply: "__applyAnnouncement"
    }
  },

  members: {
    __applyAnnouncement: function(announcement) {
      console.log("build announcements", announcement);
    }
  }
});
