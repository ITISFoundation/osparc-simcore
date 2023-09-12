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
    __checkInternval: null,
    __announcements: null,

    startTracker: function() {
      const checkAnnouncements = () => {
        osparc.data.Resources.get("announcements")
          .then(announcements => {
            if (announcements && announcements.length) {
              this.__setAnnouncements(announcements);
            } else {
              this.__setAnnouncements(null);
            }
          })
          .catch(err => console.error(err));
      };
      checkAnnouncements();
      this.__checkInternval = setInterval(checkAnnouncements, this.self().CHECK_INTERVAL);
    },

    stopTracker: function() {
      if (this.__checkInternval) {
        clearInterval(this.__checkInternval);
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
