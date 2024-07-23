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

qx.Class.define("osparc.announcement.Tracker", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    CHECK_INTERVAL: 60*60*1000 // Check every 60'
  },

  members: {
    __checkInterval: null,
    __announcements: null,

    checkAnnouncements: async function() {
      return new Promise(resolve => {
        osparc.data.Resources.get("announcements")
          .then(announcements => {
            if (announcements && announcements.length) {
              this.__setAnnouncements(announcements);
            } else {
              this.__setAnnouncements(null);
            }
            resolve();
          })
          .catch(err => console.error(err));
      });
    },

    startTracker: function() {
      this.checkAnnouncements();
      this.__checkInterval = setInterval(() => this.checkAnnouncements(), this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInterval) {
        clearInterval(this.__checkInterval);
      }
    },

    __setAnnouncements: function(announcementsData) {
      this.__announcements = {};
      if (announcementsData) {
        announcementsData.forEach(announcementData => {
          const announcement = new osparc.announcement.Announcement(announcementData);
          osparc.announcement.AnnouncementUIFactory.getInstance().setAnnouncement(announcement);
        });
      }
    }
  }
});
