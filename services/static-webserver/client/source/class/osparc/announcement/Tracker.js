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

    checkAnnouncements: async function() {
      osparc.data.Resources.get("announcements")
        .then(announcements => {
          osparc.announcement.AnnouncementUIFactory.getInstance().setAnnouncementsData((announcements && announcements.length) ? announcements : []);
        })
        .catch(err => console.error(err));
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
  }
});
