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

qx.Class.define("osparc.AnnouncementTracker", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    start: {
      check: "Date",
      init: null,
      nullable: true
    },

    end: {
      check: "Date",
      init: null,
      nullable: true
    },

    title: {
      check: "String",
      init: null,
      nullable: true
    },

    announcement: {
      check: "String",
      init: null,
      nullable: true
    }
  },

  members: {
    __loginAnnouncement: null,

    startTracker: function() {
      if (osparc.product.Utils.isProduct("s4llite")) {
        const announcementData = {
          start: "2023-06-22T15:00:00.000Z",
          end: "2023-11-01T02:00:00.000Z",
          title: "Student Competition",
          announcement: "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/' target='_blank'>here</a>"
        };
        this.__setAnnouncement(announcementData);
      }
    },

    getLoginAnnouncement: function() {
      return this.__loginAnnouncement;
    },

    __setAnnouncement: function(announcementData) {
      this.setStart(announcementData && "start" in announcementData ? new Date(announcementData.start) : null);
      this.setEnd(announcementData && "end" in announcementData ? new Date(announcementData.end) : null);
      this.setTitle(announcementData && "title" in announcementData ? announcementData.title : null);
      this.setAnnouncement(announcementData && "reason" in announcementData ? announcementData.reason : null);

      this.__buildAnnouncementUIs();
    },

    __buildAnnouncementUIs: function() {
      this.__buildLoginAnnouncement();
      this.__buildUserMenuAnnouncement();
    },

    __buildLoginAnnouncement: function() {
      this.__loginAnnouncement = new qx.ui.basic.Label(this.getTitle());
    },

    __buildUserMenuAnnouncement: function() {
    }
  }
});
